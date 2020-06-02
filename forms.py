from __future__ import unicode_literals
import pygeocoder
#from captcha.fields import ReCaptchaField   
from nocaptcha_recaptcha.fields import NoReCaptchaField
from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.tokens import default_token_generator
#from django.contrib.sites.models import get_current_site
from django.contrib.sites.shortcuts import get_current_site

from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string

import membership
import models
from common import constants
from common.validators import RangeValidator


#### SOME FORMS WERE DELETED FOR SECURITY ####

class PersonForm(forms.ModelForm):
    '''Base model form for adding/editing a Person record'''
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password Confirmation',
        widget=forms.PasswordInput)
    email_optout = forms.BooleanField(
        label="I would like to opt-out of communications from the AAVSO",
        required=False)
    user_search = forms.BooleanField(
        label="I would like other AAVSO users to be able to search for me",
        required=False)
    astronomer = forms.BooleanField(label="I am a professional astronomer",
        required=False)
    institution = forms.BooleanField(label="This account is for an institution",
        required=False)
    #latitude = CoordinateField(required=False,
    #    help_text='Accepted formats: \xb1DD:MM:SS.XX or decimal degrees'
    #              '<br>e.g. -35:32:28.12; 42.38711'
    #              '<br>Use negative values for Southern Hemisphere')
    #longitude = CoordinateField(required=False,
    #    help_text='Same format as latitude'
    #              '<br>Use negative values for Western Hemisphere')
    affiliation = forms.ModelChoiceField(queryset=models.Organization.objects,
        empty_label=None)
    howheard = forms.CharField(label="How did you hear about the AAVSO?",
        required=False, widget=forms.Textarea)
    experience = forms.CharField(label="What is your level of experience?",
        required=False, widget=forms.Textarea)
    equipment = forms.CharField(label="What equipment do you have?",
        required=False, widget=forms.Textarea)
    member_notes = forms.CharField(label="Any other notes",
        required=False, widget=forms.Textarea)
    captcha = NoReCaptchaField(label="Prove you're human")

    class Meta:
        model = models.Person
        fields = '__all__'
        exclude = ('obscode', 'member_joined', 'special_membership',
                   'observer_added', 'groups', 'is_active', 'email_validated',
                   'is_staff', 'is_superuser', 'user_permissions',
                   'last_login', 'password', 'created', 'notes',
                   'observer_notes', 'solar_obscode', 'sid_obscode',
                   'latitude', 'longitude')

    def __init__(self, *args, **kwargs):
        super(PersonForm, self).__init__(*args, **kwargs)

        # set required form fields
        if self.fields.get('username'):
            self.fields['username'].required = True
        if self.fields.get('email'):
            self.fields['email'].required = True
        if self.fields.get('country'):
            self.fields['country'].required = True

        # set date formats for birthdate field
        if self.fields.get('birthdate'):
            self.fields['birthdate'].input_formats = ('%Y-%m-%d', '%Y/%m/%d')

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 != password2:
            raise forms.ValidationError("Passwords Must Match",
                code='password_mismatch')

        return password2

    def save(self, commit=True):
        user = super(PersonForm, self).save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class PersonNameForm(PersonForm):
    '''Person form with only name fields.'''
    class Meta:
        model = models.Person
        fields = ('title', 'given_name', 'middle_name', 'family_name',
            'name_suffix')

    def __init__(self, *args, **kwargs):
        super(PersonNameForm, self).__init__(*args, **kwargs)
        self.fields['affiliation'].required = False
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        if self.fields.get('captcha'):
            del self.fields['captcha']


class PersonEditForm(PersonForm):
    '''Form for editing a person's record'''
    class Meta:
        model = models.Person
        exclude = ('obscode', 'title', 'given_name', 'middle_name',
            'family_name', 'name_suffix', 'special_membership',
            'observer_added', 'member_joined', 'council', 'staff',
            'address_invalid', 'resigned', 'deceased', 'solar_observer',
            'notes', 'observer_notes', 'password', 'password1', 'password2',
            'last_login', 'username', 'is_superuser', 'is_staff', 'captcha',
            'is_active', 'email_verified', 'created', 'sid_observer')

    def __init__(self, *args, **kwargs):
        super(PersonForm, self).__init__(*args, **kwargs)

        # set required form fields
        if self.fields.get('username'):
            self.fields['username'].required = False
        if self.fields.get('password1'):
            self.fields['password1'].required = False
        if self.fields.get('password2'):
            self.fields['password2'].required = False
        if self.fields.get('captcha'):
            del self.fields['captcha']


class FindMemberByLocation(forms.Form):
    '''Form for searching for members by a given starting point and within a specified search radius'''

    user_location_search = forms.ChoiceField(label='From your address',
                                             choices=((True, 'Yes'), (None, 'No')), required=False)
    location = forms.CharField(label="From a location", required=False,
                               help_text='enter any of City, State, Country (e.g. Cambridge, MA; London UK)')
    latitude = forms.FloatField(label="Latitude", widget=forms.TextInput(attrs={'placeholder': '(e.g. 41.88)'}),
                                required=False, help_text='in degrees North(+) | South(-)', min_value=-90, max_value=90)
    longitude = forms.FloatField(label="Longitude", widget=forms.TextInput(attrs={'placeholder': '(e.g. -88.01)'}),
                                 required=False, help_text='in degrees East(+) | West(-)', min_value=-180, max_value=180)
    search_radius = forms.IntegerField(label='Search Radius', required=True, min_value=0,
                                       initial=10, help_text='in kilometers')

    def __init__(self, *args, **kwargs):
        if 'user' in kwargs:
            self.user = kwargs['user']
            del kwargs['user']
        super(FindMemberByLocation, self).__init__(*args, **kwargs)

    def clean(self):
        data = self.cleaned_data
        geocoder = pygeocoder.Geocoder(api_key=settings.GOOGLE_API_KEY)
        if data['user_location_search']:
            if self.user.latitude and self.user.longitude:
                data['coords'] = (self.user.latitude, self.user.longitude)
            elif self.user.city or self.user.region:
                search = ','.join(
                    [self.user.city, self.user.region, self.user.country])
                try:
                    result = geocoder.geocode(search)
                    data['coords'] = result[0].coordinates
                except pygeocoder.GeocoderError:
                    raise forms.ValidationError(
                        "We could not obtain your location from our records."
                        "Please enter a location below.")
            else:
                raise forms.ValidationError(
                    "We could not obtain your location from our records."
                    "Please enter a location below.")
        elif data['location'] or data['latitude'] or data['longitude']:
            if data['location']:
                try:
                    result = geocoder.geocode(data['location'])
                    data['coords'] = result[0].coordinates
                except pygeocoder.GeocoderError:
                    msg = "Could not find location: {}".format(data['location'])
                    self._errors['location'] = self.error_class([msg])
                    del data['location']

            elif data['latitude'] and data['longitude']:
                data['coords'] = (data['latitude'], data['longitude'])
            else:
                raise forms.ValidationError(
                    "You must provide either a location or latitude/longitude")
        else:
            raise forms.ValidationError(
                "No location search type entered")

        return data


class FindMemberByUser(forms.Form):
    '''Search Form for searching for member(s) by username, obscode, or last name.
    Additional queryset parameters can be stacked
    '''

    searchterm = forms.CharField(label="Enter a username, obscode, or last name", required=False,
        help_text='')

    def __init__(self, *args, **kwargs):
        if 'user' in kwargs:
            self.user = kwargs['user']
            del kwargs['user']
        super(FindMemberByUser, self).__init__(*args, **kwargs)


### Admin Forms ###
class SearchForm(forms.Form):
    '''Advanced search form for HQ admin'''
    # General
    id__in = forms.CharField(label='Person ID', required=False,
        help_text='A comma-separated list of IDs to match')
    obscode__in = forms.CharField(label="Obscode", required=False,
        help_text='A comma-separated list of Obscodes to match')
    q = forms.CharField(label="Name", required=False)
    email__contains = forms.CharField(label='Email address', required=False)
    email_optout = forms.ChoiceField(required=False,
            choices=(
                ('', '---'),
                (1, 'Yes'),
                (0, 'No'),
            ))
    city = forms.CharField(label='City/Town', required=False)
    region = forms.CharField(label='State/Province/Region', required=False)
    country = forms.ChoiceField(choices=(('', u'-----'),) + constants.COUNTRIES,
        required=False)

    # Membership Info
    membership_status = forms.ChoiceField(choices=(
            ('', '---'),
            ('member', 'Paid Members'),
            ('notdropped', 'Members (including unpaid)'),
            ('suspended', 'Unpaid members'),
            ('nonmember', 'Non-members'),
        ),
        required=False)
    membership_year = forms.IntegerField(label='Year', required=False,
        help_text="Leave blank for current year")

    membership_type = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=(
            ('annual', 'Annual'),
            ('sustaining', 'Sustaining'),
            ('junior', 'Junior/Limited Income'),
            ('sponsored', 'Sponsored'),
            ('comp', 'Complimentary'),
            ('honorary', 'Honorary'),
            ('lifetime', 'Lifetime'),
        ),
        required=False)

    unpaid = forms.IntegerField(required=False,
        help_text="Finds everyone who hasn't paid for the given year")

    # Publications
    subscription_type = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=(
            ('journal', 'Journal'),
            ('bulletin', 'Bulletin'),
            ('solar', 'Solar Bulletin'),
            ('newsletter', 'Newsletter'),
            ('annual', 'Annual Report'),
        ),
        required=False)
    subscription_year = forms.IntegerField(required=False,
        help_text="Leave blank for current year")

    # Miscellaneous
    latitude__gte = forms.FloatField(required=False,
        validators=[RangeValidator(-90,90)])
    latitude__lte = forms.FloatField(required=False,
        validators=[RangeValidator(-90,90)])
    longitude__gte = forms.FloatField(required=False,
        validators=[RangeValidator(-180,180)])
    longitude__lte = forms.FloatField(required=False,
        validators=[RangeValidator(-180,180)])

    # HQ
    notes__contains = forms.CharField(label="Notes", required=False)
    member_joined__gte = forms.DateField(required=False)
    member_joined__lte = forms.DateField(required=False)
    observer_added__gte = forms.DateField(required=False)
    observer_added__lte = forms.DateField(required=False)

    astronomer = forms.ChoiceField(required=False,
        choices=(('', '---'), (1, 'Yes'), (0, 'No'),))
    institution = forms.ChoiceField(required=False,
        choices=(('', '---'), (1, 'Yes'), (0, 'No'),))
    council = forms.ChoiceField(required=False,
        choices=(('', '---'), (1, 'Yes'), (0, 'No'),))
    staff = forms.ChoiceField(required=False,
        choices=(('', '---'), (1, 'Yes'), (0, 'No'),))
    address_invalid = forms.ChoiceField(required=False,
        choices=(('', '---'), (1, 'Yes'), (0, 'No'),))
    deceased = forms.ChoiceField(required=False,
        choices=(('', '---'), (1, 'Yes'), (0, 'No'),))
    solar_observer = forms.ChoiceField(required=False,
        choices=(('', '---'), (1, 'Yes'), (0, 'No'),))


