from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView, TemplateView
from library import views

admin.site.site_header = 'Шаг · управление библиотекой'
admin.site.site_title = 'Шаг'
urlpatterns = [
    path('', RedirectView.as_view(pattern_name='catalog', permanent=False)),
    path('materials/', views.catalog, name='catalog'),
    path('materials/<slug:slug>/', views.detail, name='detail'),
    path('materials/<slug:slug>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('files/<int:pk>/', views.attachment, name='attachment'),
    path('covers/<int:pk>/', views.cover, name='cover'),
    path('favorites/', views.favorites, name='favorites'),
    path('accounts/login/', views.SignInView.as_view(), name='login'),
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),
    path('admin/', admin.site.urls),
]
