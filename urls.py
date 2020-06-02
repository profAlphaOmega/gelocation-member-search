from __future__ import unicode_literals
from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
import views

urlpatterns = [
    url(r'^$',
        login_required(TemplateView.as_view(template_name='hq/profile.html')),
        name='profile'),
    url(r'^request_obscode/', views.request_obscode, name='request_obscode'),
    url(r'^edit_profile/', views.edit_profile, name='edit_profile'),
    url(r'^search/', login_required(views.UserSearch.as_view()), name='search'),
]
