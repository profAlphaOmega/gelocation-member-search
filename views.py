from __future__ import unicode_literals

import logging
import pygeocoder
from collections import OrderedDict
from copy import deepcopy
from datetime import date
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail, EmailMessage
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.template.context import RequestContext
from django.template.loader import render_to_string
from django.views.generic import View

import forms
import models
from common import constants
from utils import payment
from utils.getdate import current_date
from utils.obscode import GenObscodeError
from adoptastar.models import ADOPT_COST

from pyproj import Geod

logger = logging.getLogger('aavso.hq')



################################################################################
## MANY VIEWS WERE DELETED FOR SECURITY PURPOSES ##
################################################################################
@login_required
def request_obscode(request):
    '''View to assign user an obscode

    This page generates an obscode and assigns it to the logged-in user.
    Once the obscode is assigned, the following happens:
    * It's logged
    * A confirmation email is sent to staff
    * The user is redirected to their profile with a success message

    If the user is not logged in, redirects to login page.
    If the user already has an obscode, they're redirected to their profile
    page with a message that they already have an obscode.
    '''
    user = request.user

    # already has obscode
    if user.obscode:
        messages.info(request, 'You already have an obscode')
        return redirect('hq:profile')

    # generate obscode
    try:
        user.assign_obscode()

        logger.info("Obscode: assigned {obscode} to {user}({id})"
            .format(obscode=user.obscode, user=user, id=user.id))

        send_mail(
            subject='[AAVSO-Web] Obscode Assigned',
            message=render_to_string('hq/email/obscode.txt', {'user': user}),
            from_email='no-reply@aavso.org',
            recipient_list=[settings.EMAIL['new observer']])

        messages.success(request,
            'You have been assigned an obscode: ' + user.obscode)
        request.user.save()

    except GenObscodeError as e:
        messages.error(request, e.message)

    return redirect('hq:profile')



# User search tool
class UserSearch(View):
    '''Find Member(s) by either username, obscode, or last name, or find by user specified starting location'''

    def get(self, request):
        if not request.user.has_member_privileges:
            request.message.warning(
                'You need to be a member if you want to search for AAVSOers!')
            return redirect("hq:profile")

        usersearchform = forms.FindMemberByUser()
        locationsearchform = forms.FindMemberByLocation()


        ### USER SEARCH
        usersearch = request.GET.get('usersearch')
        if usersearch:
            searchterm = request.GET.get('searchterm')
            if not searchterm:
                messages.error(request, "No Member info entered.")

            results = models.Person.find_by_user(searchterm)
            usersearchform = forms.FindMemberByUser(initial={'searchterm': searchterm})
            locationsearchform = forms.FindMemberByLocation()
            return render(request, "hq/findmember.html",
                        {
                            'usersearchform': usersearchform,
                            'locationsearchform': locationsearchform,
                            'found_by_username_flag': True,
                            'found_members': results
                        }
                          )


        ### LOCATION SEARCH
        userlocation = request.GET.get('userlocation')
        if userlocation:
            geocoder = pygeocoder.Geocoder(api_key=settings.GOOGLE_API_KEY)

            search_radius = float(request.GET.get('search_radius'))
            location = request.GET.get('location')
            latitude = request.GET.get('latitude')
            longitude = request.GET.get('longitude')
            r_latitude = latitude
            r_longitude = longitude
            user_location_search = request.GET.get('user_location_search')
            if user_location_search:
                if request.user.latitude and request.user.longitude:
                    latitude = float(request.user.latitude)
                    longitude = float(request.user.longitude)
                elif request.user.city or request.user.region:
                    search = ','.join(
                    [request.user.city, request.user.region, request.user.country])
                    try:
                        result = geocoder.geocode(search)
                        latitude, longitude = result[0].coordinates
                    except pygeocoder.GeocoderError:
                        messages.error(request, "Can not find your location from our records")
                        redirect("hq:search")
                else:
                    messages.error(request, "Can not find your location from our records")
                    redirect("hq:search")
            elif location or latitude or longitude:
                if location:
                    try:
                        result = geocoder.geocode(location)
                        latitude, longitude = result[0].coordinates
                    except pygeocoder.GeocoderError:
                        messages.error(request, "Could not find your entered location, please try another.")
                        redirect("hq:search")
                elif latitude and longitude:
                    latitude = float(latitude)
                    longitude = float(longitude)
                else:
                    messages.error(request, "Please enter both Latitude and Longitude")
                    redirect("hq:search")
            else:
                messages.error(request, "No location search criteria entered")
                redirect("hq:search")
            if latitude and longitude and search_radius:
                try:
                    results = models.Person.find_by_coordinates(latitude, longitude, search_radius)
                    usersearchform = forms.FindMemberByUser()
                    locationsearchform = forms.FindMemberByLocation(initial={
                        'user_location_search': user_location_search,
                        'search_radius': search_radius,
                        'location': location,
                        'latitude': r_latitude,
                        'longitude': r_longitude,
                    })
                    return render(request, "hq/findmember.html",
                          {
                              'usersearchform': usersearchform,
                              'locationsearchform': locationsearchform,
                              'found_by_coordinates_flag': True,
                              'found_members': results
                          })
                except:
                    redirect("hq:search")

        return render(request, "hq/findmember.html",
                      {
                          'usersearchform': usersearchform,
                          'locationsearchform': locationsearchform
                      }
                    )
