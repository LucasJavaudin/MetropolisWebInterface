from django.urls import path, re_path

from . import views

app_name = 'metro'
urlpatterns = [
    #Lucas Hornung
    path(r'events_view', views.show_events, name='events_view'),
    path(r'events_view/add_event', views.create_event, name='events_add'),
    re_path(r'delete_event/(?P<pk>[0-9]+)/', views.delete_event,
            name='events_delete'),
    re_path(r'events_view/edit_event/show/(?P<pk>[0-9]+)',
            views.edit_event_show, name='events_edit_show'),
    re_path(r'events_view/edit_event/edit/(?P<pk>[0-9]+)', views.edit_event,
            name='events_edit'),
    path(r'articles_view', views.show_articles, name='articles_view'),
    re_path(r'^articles/(?P<path>.*)$', views.download_article_file,
            name='article_file_download'),
    path(r'articles_view/add_article', views.create_article,
         name='articles_add'),
    re_path(r'delete_article/(?P<pk>[0-9]+)/', views.delete_article,
            name='articles_delete'),
    path(r'<simulation_id>/export/', views.simulation_export,
         name='simulation_export'),
    path(r'<simulation_id>/demand/<demandsegment_id>/export/',
         views.usertype_export, name='usertype_export'),
    path(r'environments',
         views.environments_view, name='environments_view'),
    path(r'environments/create',
         views.environment_create, name='environments_create'),
    re_path(r'environments/add_view/(?P<pk>[0-9]+)',
         views.environment_add_view, name='environments_add_view'),
    re_path(r'environments/add/(?P<environment>[0-9]+)',
         views.environment_add, name='environments_add'),
    re_path(r'environments/(?P<environment>[0-9]+)/(?P<user>[0-9]+)',
         views.environment_user_delete, name='environment_user_delete'),

    #Lucas Javaudin
    path(r'',
        views.simulation_manager, name='simulation_manager'),
    path(r'<simulation_id>/view',
        views.simulation_view, name='simulation_view'),
    path(r'<simulation_id>/export',
        views.simulation_export, name='simulation_export'),
    path(r'<simulation_id>/save',
        views.simulation_view_save, name='simulation_view_save'),
    path(r'<simulation_id>/edit',
        views.simulation_view_edit, name='simulation_view_edit'),
    path(r'howto',
        views.how_to, name='how_to'),
    path(r'tutorial',
        views.tutorial, name='tutorial'),
    path(r'contributors',
        views.contributors, name='contributors'),
    path(r'disqus',
        views.disqus, name='disqus'),
    path(r'<simulation_id>/demand/',
        views.demand_view, name='demand_view'),
    path(r'<simulation_id>/demand/add',
        views.usertype_add, name='usertype_add'),
    path(r'<simulation_id>/demand/<demandsegment_id>/edit/',
        views.usertype_edit, name='usertype_edit'),
    path(r'<simulation_id>/demand/<demandsegment_id>/edit/save/',
        views.usertype_edit_save, name='usertype_edit_save'),
    path(r'<simulation_id>/demand/<demandsegment_id>/delete/',
        views.usertype_delete, name='usertype_delete'),
    path(r'<simulation_id>/demand/<demandsegment_id>/view/',
        views.usertype_view, name='usertype_view'),
    path(r'<simulation_id>/network/',
        views.network_view, name='network_view'),
    path(r'<simulation_id>/run/<run_id>/network',
        views.network_view_run, name='network_view_run'),
    path(r'<simulation_id>/matrices/<demandsegment_id>/',
        views.matrix_main, name='matrix_main'),
    path(r'<simulation_id>/matrices/<demandsegment_id>/view/',
        views.matrix_view, name='matrix_view'),
    path(r'<simulation_id>/matrices/<demandsegment_id>/edit/',
        views.matrix_edit, name='matrix_edit'),
    path(r'<simulation_id>/matrices/<demandsegment_id>/import/',
        views.matrix_import, name='matrix_import'),
    path(r'<simulation_id>/matrices/<demandsegment_id>/export/',
        views.matrix_export, name='matrix_export'),
    path(r'<simulation_id>/matrices/<demandsegment_id>/save/',
        views.matrix_save, name='matrix_save'),
    path(r'<simulation_id>/matrices/<demandsegment_id>/reset/',
        views.matrix_reset, name='matrix_reset'),
    path(r'<simulation_id>/pricing/',
        views.pricing_main, name='pricing_main'),
    path(r'<simulation_id>/pricing/view/',
        views.pricing_view, name='pricing_view'),
    # path(r'<simulation_id>/pricing/edit/',
        # views.pricing_edit, name='pricing_edit'),
    path(r'<simulation_id>/pricing/save/',
        views.pricing_save, name='pricing_save'),
    path(r'<simulation_id>/pricing/export/',
        views.pricing_export, name='pricing_export'),
    path(r'<simulation_id>/pricing/import/',
        views.pricing_import, name='pricing_import'),
    path(r'<simulation_id>/pricing/reset/',
        views.pricing_reset, name='pricing_reset'),
    path(r'copy',
        views.copy_simulation, name='copy_simulation'),
    path(r'add/action',
        views.simulation_add_action, name='simulation_add_action'),
    path(r'<simulation_id>/delete',
        views.simulation_delete, name='simulation_delete'),
    path(r'<simulation_id>/run/action',
        views.simulation_run_action, name='simulation_run_action'),
    path(r'<simulation_id>/run/<run_id>/stop',
        views.simulation_run_stop, name='simulation_run_stop'),
    path(r'<simulation_id>/run/<run_id>',
        views.simulation_run_view, name='simulation_run_view'),
    path(r'<simulation_id>/run_list',
        views.simulation_run_list, name='simulation_run_list'),
    path(r'<simulation_id>/run/<run_id>/link_output',
        views.simulation_run_link_output, name='simulation_run_link_output'),
    path(r'<simulation_id>/run/<run_id>/user_output',
        views.simulation_run_user_output, name='simulation_run_user_output'),
    path(r'register',
        views.register, name='register'),
    path(r'register/action',
        views.register_action, name='register_action'),
    path(r'login/error',
        views.login_view, {'login_error': True}, name='login'),
    path(r'login',
        views.login_view, name='login'),
    path(r'login/action',
        views.login_action, name='login_action'),
    path(r'logout',
        views.logout_action, name='logout'),
    path(r'password_reset',
        views.PasswordResetView.as_view(), name='password_reset'),
    path(r'password_reset_done',
        views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path(r'password_reset_confirm/<uidb64>/<token>/',
        views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path(r'<simulation_id>/public_transit/',
        views.public_transit_view, name='public_transit_view'),
    path(r'<simulation_id>/public_transit/list',
        views.public_transit_list, name='public_transit_list'),
    path(r'<simulation_id>/public_transit/edit/save',
        views.public_transit_edit_save, name='public_transit_edit_save'),
    path(r'<simulation_id>/public_transit/edit',
        views.public_transit_edit, name='public_transit_edit'),
    path(r'<simulation_id>/public_transit/delete',
        views.public_transit_delete, name='public_transit_delete'),
    path(r'<simulation_id>/public_transit/import',
        views.public_transit_import, name='public_transit_import'),
    path(r'<simulation_id>/public_transit/export',
        views.public_transit_export, name='public_transit_export'),
    path(r'<simulation_id>/object/<object>[a-z]+/',
        views.object_view, name='object_view'),
    path(r'<simulation_id>/object/<object>[a-z]+/list/',
        views.object_list, name='object_list'),
    # For some reason object_edit_save must be declared before object_edit...
    path(r'<simulation_id>/object/<object>[a-z]+/edit/save',
        views.object_edit_save, name='object_edit_save'),
    path(r'<simulation_id>/object/<object>[a-z]+/edit/',
        views.object_edit, name='object_edit'),
    path(r'<simulation_id>/object/<object>[a-z]+/delete/',
        views.object_delete, name='object_delete'),
    path(r'<simulation_id>/object/<object>[a-z]+/import/',
        views.object_import, name='object_import'),
    path(r'<simulation_id>/object/<object>[a-z]+/export/',
        views.object_export, name='object_export'),
    path(r'<simulation_id>/demand/import', views.usertype_import, name='usertype_import'),
]
