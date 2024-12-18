from django.urls import path
from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search, name="search"),
    path("stats/", views.stats, name="stats"),
    path('test-db/', views.test_db, name='test_db'),
]
