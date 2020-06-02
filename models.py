from __future__ import unicode_literals

import datetime
import MySQLdb as mysql
import pygeocoder
import pyproj
from collections import OrderedDict
from datetime import date
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver

from common import constants
from common import validators
from common.models import Observation
from utils.getdate import current_date
from utils.obscode import generate_obscode

# Monkeypatch to allow us to use 0 in auto_increment values in MySQL
# This behavior was made impossible in Django 1.6 due to MySQL's default
# behavior but did not take into account that 0 keys are possible when MySQL
# is configured with NO_AUTO_VALUE_ON_ZERO.
# c.f. https://code.djangoproject.com/ticket/17653
#
# This is necessary because at least one legacy table, specifically the
# Organization model below, uses a 0 id and this is not easily changed without
# affecting other data.
# TODO This should be removed if future Django versions provide the ability
# to use 0 pk values in MySQL
# (or, even better, if the data can be updated to not rely on a 0 pk value)
import django.db.backends.mysql.base
django.db.backends.mysql.base.DatabaseOperations.validate_autopk_value = (
    lambda self, x: x)


class PersonManager(BaseUserManager):
    '''Custom User Manager for Person model'''
    def create_user(self, username, given_name, family_name, email,
            password=None, **extra_fields):
        email = self.normalize_email(email)
        user = self.model(username=username,
                          given_name=given_name,
                          family_name=family_name,
                          email=email,
                          **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, given_name, family_name, email,
            password, **extra_fields):
        if not username:
            raise ValueError('Must supply username for superuser')
        email = self.normalize_email(email)
        user = self.model(username=username,
                          given_name=given_name,
                          family_name=family_name,
                          email=email,
                          is_staff=True,
                          is_superuser=True,
                          **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class Person(AbstractBaseUser, PermissionsMixin):
    '''Unified record for storing members, observers and website logins

    This model is the custom auth user model for the AAVSO website. See the
    Django documenetation for more details.
    '''
    username = models.CharField(max_length=60, unique=True, blank=True,
        null=True)
    # do not confuse with 'staff' field below, which designates AAVSO staff
    is_staff = models.BooleanField(
        'admin status',
        db_column='is_admin',
        default=False,
        help_text = "Designates whether the user can log into this admin site."
    )
    is_active = models.BooleanField('active', default=True,
        help_text='Designates whether the user is active. Uncheck to block the'
                  ' user from logging in.')
    email_verified = models.BooleanField('email verified', default=False,
        help_text='Designates whether the user has verified their email'
                  ' address.')

    obscode = models.CharField(max_length=6, unique=True, blank=True,
        null=True, validators=[validators.validate_obscode])

    # Name fields
    title = models.CharField(max_length=25, blank=True,
        help_text='e.g. Dr., Mr., Mrs.')
    given_name = models.CharField(max_length=255)
    middle_name = models.CharField("middle name(s)", max_length=255, blank=True)
    family_name = models.CharField("family name / surname", max_length=255)
    name_suffix = models.CharField(max_length=25, blank=True)

    # Contact information
    organization = models.CharField(max_length=255, blank=True,
        help_text='Any line in your address, before the street, goes here')
    address1 = models.CharField("street address line 1", max_length=255,
        blank=True)
    address2 = models.CharField("street address line 2", max_length=255,
        blank=True)
    city = models.CharField("city / town", max_length=255, blank=True)
    region = models.CharField("state / province / region", max_length=32,
        blank=True, help_text='Use two-letter state/province code in US/Canada')
    postal = models.CharField("ZIP / postal code", max_length=32, blank=True)
    country = models.CharField(max_length=3, choices=constants.COUNTRIES,
        blank=True)
    phone1 = models.CharField("phone", max_length=30, blank=True)
    phone2 = models.CharField("other phone", max_length=30, blank=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    email_optout = models.BooleanField(default=False)
    user_search = models.BooleanField("user search opt-in", default=False)

    # Headquarters Info
    special_membership = models.CharField(max_length=12,
        choices=(
            ('honorary', 'Honorary'),
            ('lifetime', 'Lifetime'),
        ),
        blank=True)
    created = models.DateField(default=datetime.date.today)
    updated = models.DateField(auto_now=True)
    observer_added = models.DateField(blank=True, null=True)
    member_joined = models.DateField(blank=True, null=True)
    astronomer = models.BooleanField(default=False)
    institution = models.BooleanField(default=False)
    council = models.BooleanField(default=False)
    staff = models.BooleanField(default=False)
    address_invalid = models.BooleanField(default=False)
    resigned = models.BooleanField(default=False)
    deceased = models.BooleanField(default=False)
    solar_observer = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    observer_notes = models.TextField(blank=True)
    solar_obscode = models.CharField(max_length=6, unique=True, blank=True,
        null=True)
    sid_obscode = models.CharField(max_length=6, unique=True, blank=True,
        null=True)

    # Miscellaneous Info
    latitude = models.FloatField(blank=True, null=True,
        validators=[validators.RangeValidator(-90,90)])
    longitude = models.FloatField(blank=True, null=True,
        validators=[validators.RangeValidator(-180,180)])
    profession = models.CharField(max_length=64, blank=True)
    affiliation = models.ForeignKey("Organization")
    nickname = models.CharField(max_length=64, blank=True)
    birthdate = models.DateField(help_text='Use YYYY-MM-DD format', blank=True,
        null=True)
    howheard = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    equipment = models.TextField(blank=True)
    member_notes = models.TextField(blank=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['given_name', 'family_name', 'email']
    objects = PersonManager()

    class Meta:
        verbose_name_plural = 'people'

    def __init__(self, *args, **kwargs):
        super(Person, self).__init__(*args, **kwargs)
        self.today = current_date()

    def __unicode__(self):
        return "({}) {} {}".format(self.id, self.given_name, self.family_name)

    def save(self, *args, **kwargs):
        # These fields must be saved as NULL in the database if left blank
        if not self.email:
            self.email = None
        if not self.username:
            self.username = None
        if not self.obscode:
            self.obscode = None
        if not self.solar_obscode:
            self.solar_obscode = None
        if not self.sid_obscode:
            self.sid_obscode = None

        if self.city:
            self.set_coordinates()
        else:
            self.latitude = self.longitude = None

        super(Person, self).save(*args, **kwargs)

    ## Auth ##
    def get_short_name(self):
        return self.username

    def get_full_name(self):
        fields = [self.title,
                  self.given_name if self.given_name != '.' else '',
                  self.middle_name,
                  self.family_name,
                  self.name_suffix]

        return u' '.join([x for x in fields if x])

    def location_disp(self):
        loc = []
        if self.city:
            loc.append(self.city)
        if self.region:
            loc.append(self.region)
        if self.country:
            loc.append(self.country)
        return ', '.join(loc)

    ### Membership ###
    # TODO remove this?
    membership_types = OrderedDict((
        ('annual',     {'label': 'Annual', 'cost': 5.00}),
        ('sustaining', {'label': 'Sustaining', 'cost': 10.00}),
        ('junior',     {'label': 'Junior/Limited Income', 'cost': 2.50}),
    ))

    def allow_renewal(self):
        '''Check if membership renewal for the next year is allowed

        Currently returns False before April 1st and True afterwards.
        '''
        return self.today.month >= 4

    @property
    def last_payment(self):
        '''Get the person's most recent payment'''
        payments = self.payment_set.order_by('-end')
        if payments.count():
            return payments[0]
        return None

    def is_member(self):
        '''Check if the person is currently a member in good standing

        A person is a member until the April 1st following the year of their
        payment. E.g. if someone is paid through 12-31-2013, they are a
        member until 4-1-2014.
        '''
        last = self.last_payment
        if last:
            suspend_date = date(last.end.year+1, 4, 1)
            if self.today < suspend_date:
                return True

        if self.special_membership:
            return True

        return False

    def is_suspended(self):
        '''Check if a person is suspended.

        A person is suspended the April 1 after their payment ends. They
        remain suspended until the end of that year, at which time they
        are no longer a member.'''
        if self.special_membership:
            return False

        last = self.last_payment
        if last:
            suspend_date = date(self.last_payment.end.year+1, 4, 1)
            drop_date = date(self.last_payment.end.year+2, 1, 1)
            return (self.today >= suspend_date and self.today < drop_date)

        return False

    def has_member_privileges(self):
        '''Check if a person has member privileges.'''
        return self.staff or self.is_member()

    def membership_type(self):
        '''Get the user's current membership type'''
        if not (self.is_member() or self.is_suspended()):
            return 'non-member'
        if self.special_membership:
            return self.special_membership
        else:
            return self.last_payment.type

    def membership_type_display(self):
        '''Get the display value for the user's current membership type'''
        if not (self.is_member() or self.is_suspended()) :
            return 'Non-member'
        if self.special_membership:
            return self.get_special_membership_display()
        else:
            return self.last_payment.get_type_display()

    def years_owed(self):
        '''Get the years the user currently owes dues for'''
        return [x for x in (self.owe_current_year(), self.owe_next_year())
                if x]

    def owe_current_year(self):
        '''Returns True if the user owes dues for current year'''
        # special members don't owe dues
        if self.special_membership:
            return False

        if self.last_payment and self.last_payment.end.year < self.today.year:
            return True

        return False

    def owe_next_year(self):
        '''If registration is open for next year, and the user has not paid
        for next year, returns True; False otherwise.'''
        # special members don't owe dues
        if self.special_membership:
            return False

        if (self.last_payment and
                self.last_payment.end.year < (self.today.year + 1)):
            return self.allow_renewal()

        return False

    ### Observer ###
    def assign_obscode(self):
        '''Generate an obscode and assign it to the user.

        Also sets the observer_added date
        '''
        self.obscode = generate_obscode(
            self.given_name, self.middle_name, self.family_name, self.__class__)
        self.observer_added = date.today()

    @property
    def observations(self):
        '''Person's observations
        Returns a QuerySet representing the person's observations. Returns
        None if the user does not have an obscode.
        '''
        if self.obscode:
            return Observation.objects.filter(obscode=self.obscode)

    def find_similar(self):
        '''Returns a queryset of records in the database similar to this one.

        Used to prevent people from registering twice.
        '''
        return Person.objects.filter(
            given_name__istartswith=self.given_name[0],
            family_name=self.family_name,
        )

    @classmethod
    def find_by_coordinates(cls, latitude, longitude, dist):
        '''Search for people within a search radius

        Returns all People within dist km of the given coordinates. Only
        returns objects that have a valid latitude/longitude field filled out.
        Args:
            latitude: latitude to search, as a float
            longitude: longitude to search, as a float
            dist: distance from coordinates to search, in km
        Returns:
            A list of Person objects found within the search radius
            These user objects also have a "dist" member added with the
            distance from the search point.
        '''
        users = (cls.objects
                .filter(user_search=True, deceased=False)
                .exclude(Q(latitude=None) | Q(longitude=None))
                .exclude(username=None))

        results = []
        geo_obj = pyproj.Geod(ellps='WGS84')
        for user in users:
            try:
                dist_between = geo_obj.inv(
                    longitude, latitude, user.longitude, user.latitude)
                dist_between_km = round(dist_between[2] / 1000, 0)
                if dist_between_km <= dist:
                    user.dist = dist_between_km
                    user.dist_mi = dist_between_km * 0.621371
                    results.append(user)
            except ValueError:
                pass
        return results

    @classmethod
    def find_by_user(cls, searchterm):
        '''Search for people by username, obscode, or family_name.
        Keep adding fields to expand accepted searchterms   '''
        try:
            results = (cls.objects
                       .filter(user_search=True, deceased=False)
                       .filter(Q(username=searchterm) | Q(obscode=searchterm) | Q(family_name=searchterm)))
        except cls.DoesNotExist:
            results = None  # set to empty if no search results come back
        return results

    @classmethod
    def find_by_obscode(cls, searchterm):
        '''Search for people by only obscode '''
        try:
            results = (cls.objects
                       .filter(user_search=True, deceased=False)
                       .filter(Q(obscode=searchterm)))
        except cls.DoesNotExist:
            results = None  # set to empty if no search results come back
        return results

    def drupal_id(self):
        '''Get the drupal uid for this record'''
        if self.username and hasattr(settings, 'DRUPAL_DB'):
            with mysql.connect(charset='utf8', use_unicode=True,
                    **settings.DRUPAL_DB) as cur:
                cur.execute("SELECT uid FROM users WHERE name=%s",
                    (self.username,))
                res = cur.fetchall()
                if len(res):
                    return res[0][0]
        return None

    def drupal_has_permission(self, p_code):
        '''Does the current user have the perimission specified by the p_code
           The list of roles and codes is available in the aavso_live.role table '''
        # don't use drupal_id so we can reuse the connection
        if self.username and hasattr(settings, 'DRUPAL_DB'):
            with mysql.connect(charset='utf8', use_unicode=True,
                               **settings.DRUPAL_DB) as cur:
                cur.execute("SELECT uid FROM users WHERE name=%s",
                            (self.username,))
                res = cur.fetchall()
                if len(res):
                    duid = res[0][0]
                    cur.execute("SELECT * FROM users_roles where uid=%s and rid=%s", (duid, p_code))
                    res = cur.fetchall()
                    return res
        return None 

    def drupal_is_admin(self):
        '''Get the drupal uid for this record'''
        if self.username and hasattr(settings, 'DRUPAL_DB'):
            with mysql.connect(charset='utf8', use_unicode=True,
                               **settings.DRUPAL_DB) as cur:
                cur.execute("SELECT uid FROM users WHERE name=%s",
                            (self.username,))
                res = cur.fetchall()
                if len(res):
                    duid = res[0][0]
                    cur.execute("SELECT * FROM users_roles where uid=%s and (rid=39 or rid=36)", (duid,))
                    res = cur.fetchall()
                    return res
        return None
        
    def drupal_id_to_django(self):
        '''Get the drupal uid for this record'''
        if self.username and hasattr(settings, 'DRUPAL_DB'):
            with mysql.connect(charset='utf8', use_unicode=True,
                               **settings.DRUPAL_DB) as cur:
                cur.execute("SELECT uid FROM users WHERE name=%s",
                            (self.username,))
                res = cur.fetchall()
                if len(res):
                    duid = res[0][0]
                    cur.execute("SELECT * FROM users_roles where uid=%s and (rid=39 or rid=36)", (duid,))
                    res = cur.fetchall()
                    return res
        return None



    def set_coordinates(self):
        '''Set latitude and longitude from given address

        Uses a geocoding lookup based on the user's contact info to set
        their latitude/longitude fields. If the geocode lookup fails this does
        nothing.
        Args:
            no_overwrite: if this is True, this function will not overwrite
            the lat/long values if they already exist.
        '''
        geocoder = pygeocoder.Geocoder(api_key=settings.GOOGLE_API_KEY)
        try:
            result = geocoder.geocode(
                ','.join([self.city, self.region, self.country]))
            self.latitude, self.longitude = result[0].coordinates
        except pygeocoder.GeocoderError:
            self.latitude = self.longitude = None

