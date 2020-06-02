from __future__ import unicode_literals

import csv
import urllib
from datetime import date
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin.views.main import ChangeList
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db.models import Count, Max
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.html import escape

import adoptastar.models
import forms
import models
import subscriptions.models
from aavso_site.admin import aavso_admin



################################################################################
# Forms
################################################################################
class PersonEditForm(forms.forms.ModelForm):
    '''Form for updating Person record'''
    password = ReadOnlyPasswordHashField(label="Password",
        help_text="Raw passwords are not stored, so there is no way to see "
                  "this user's password, but you can change the password "
                  "using <a href=\"password/\">this form</a>.")

    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        return self.initial.get("password", "!invalid")


################################################################################
# ModelAdmin classes
################################################################################
def _show_obscode(obj):
    return obj.obscode or ''
_show_obscode.short_description = 'obscode'


@admin.register(models.Person, site=aavso_admin)
class PersonAdmin(admin.ModelAdmin):
    '''ModelAdmin class for Person model

    Advanced search is created using the search_form view to display the
    MemberSearch form; the form redirects to the model's changelist page
    using the filter API provided by the Django admin. Additional filters
    are defined using the API and must be added to list_filter; to prevent a
    filter showing up in the filter sidebar, set its template attribute to
    "admin/empty_filter.html"
    '''
    fieldsets = (
        (None, {
            'fields': ('id', 'obscode'),
        }),
        ('Name', {
            'fields': (('given_name', 'title'), ('middle_name', "name_suffix"),
                'family_name',),
        }),
        ('Contact Information', {
            'fields': ('organization', 'address1', 'address2', 'city',
                'region', 'postal', 'country', ('phone1', 'phone2'),
                ('email', 'email_optout', 'user_search')),
        }),
        ('HQ Information', {
            #'classes': ('collapse',),
            'fields': (
                ('created', 'updated', 'observer_added', 'member_joined'),
                'notes', ('astronomer', 'institution', 'council',
                'staff', 'address_invalid', 'resigned', 'deceased',
                'solar_observer'), 'special_membership',
                ('solar_obscode', 'sid_obscode')),
        }),
        ('Miscellaneous Information', {
            #'classes': ('collapse',),
            'fields': (('latitude', 'longitude'), 'affiliation',
                'profession', 'nickname', 'birthdate', 'howheard',
                'experience', 'equipment', 'member_notes', 'observer_notes',),
        }),
        ('Website User', {
            'fields': ('username', 'password', 'email_verified'),
        }),
        ('Website Permissions', {
            'fields': ('is_active', ('is_staff', 'is_superuser'), 'groups',
                'user_permissions')
        }),
    )
    form = PersonEditForm
    change_password_form = AdminPasswordChangeForm
    readonly_fields = ('id', 'updated')
    filter_horizontal = ('groups', 'user_permissions')
    inlines = (
        AwardInline,
        ObsAwardInline,
        MemberCertificationInline,
        PaymentInline,
        SubscriptionInline,
        SubscriptionAppInline,
        DonationInline,
        AdoptedInline)

    list_display = ('get_full_name', 'id', 'username', 'email', _show_obscode)
    list_filter = (
        MemberFilter,
        MemberYearFilter,
        UnpaidFilter,
        MemberTypeFilter,
        SubscriptionTypeFilter,
        SubscriptionYearFilter,
        NoNameFilter,
        LastNameOrderFilter,
        ObscodeOrderFilter,
    )
    search_fields = ('given_name', 'middle_name','family_name', 'nickname',
        'email', 'obscode', 'username')

    change_list_template = 'hq/member_changelist.html'

    def get_urls(self):
        urlpatterns = [
            url(r'^search', self.search_view, name="member_search"),
            url(r'^export', self.export_view, name="member_export"),
            url(r'^(\d+)/password/$',
                 self.admin_site.admin_view(self.user_change_password)),
        ]
        return urlpatterns + super(PersonAdmin, self).get_urls()

    def search_view(self, request):
        '''Advanced search page'''
        form = forms.SearchForm(request.GET or None)
        if form.is_valid():
            params = {}
            for k, v in form.cleaned_data.iteritems():
                if not v:
                    continue
                if isinstance(v, (list, tuple)):
                    v = ','.join(v)
                params[k] = v
            params = urllib.urlencode(params)
            return HttpResponseRedirect(
                reverse("admin:hq_person_changelist")+'?'+params)
        return render(request, "hq/search_form.html", locals())

    def export_view(self, request):
        cl = ChangeList(request, self.model, self.list_display,
            self.list_display_links, self.list_filter, self.date_hierarchy,
            self.search_fields, self.list_select_related, self.list_per_page,
            self.list_max_show_all, self.list_editable, self)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=people.csv'

        writer = csv.writer(response)
        fields = ['full_name', 'organization', 'address1', 'address2',
            'city', 'region', 'postal', 'country', 'email', 'obscode']
        writer.writerow(fields)

        for person in cl.queryset:
            row = [person.get_full_name(), person.organization, person.address1,
                   person.address2, person.city, person.region, person.postal,
                   person.get_country_display(), person.email,
                   person.obscode or '']
            utfrow = [unicode(x).encode('utf8') for x in row]
            writer.writerow(utfrow)

        return response

    # This view stolen from UserAdmin class
    def user_change_password(self, request, id, form_url=''):
        if not self.has_change_permission(request):
            raise PermissionDenied
        user = get_object_or_404(self.get_queryset(request), pk=id)
        form = self.change_password_form(user, request.POST or None)
        if form.is_valid():
            form.save()
            change_message = self.construct_change_message(request, form, None)
            self.log_change(request, request.user, change_message)
            msg = 'Password changed successfully.'
            messages.success(request, msg)
            return HttpResponseRedirect('..')

        fieldsets = [(None, {'fields': list(form.base_fields)})]
        adminForm = admin.helpers.AdminForm(form, fieldsets, {})

        context = {
            'title': 'Change password: %s' % escape(user.get_username()),
            'adminForm': adminForm,
            'form_url': form_url,
            'form': form,
            'is_popup': IS_POPUP_VAR in request.REQUEST,
            'add': True,
            'change': False,
            'has_delete_permission': False,
            'has_change_permission': True,
            'has_absolute_url': False,
            'opts': self.model._meta,
            'original': user,
            'save_as': False,
            'show_save': True,
        }
        return render(request,
            'admin/auth/user/change_password.html',
            context, current_app=self.admin_site.name)


################################################################################
# Register Admin Models
################################################################################
aavso_admin.register(models.Award)
aavso_admin.register(models.ObsAward)
aavso_admin.register(models.Organization)
aavso_admin.register(models.Certification)
aavso_admin.register(models.Fund)
