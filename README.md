

# User Geolocation Lookup

> Used for Members to lookup other members and communicate and meetup with

Used for members of AAVSO to lookup other members by name or within a radial distance from a member's location on file or a given location. The service utilizes Google Geolocation library and the Membership database. 



> There has been some coded redacted/deleted from this App for security purposes. This repos is to highlight the functional code that was developed and not ALL the code that makes the App work.

# Table of Contents 


- [Features](#features)


---

## Core Code Sections
### UserSearch `/views.py` 

```python
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

```

### Find Member by Location `/forms.py` 


```python
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

```

