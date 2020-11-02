"""This file defines the views of the website.
test
Author: Lucas Javaudin
E-mail: lucas.javaudin@ens-paris-saclay.fr
"""
import time
import re
import os
import shutil
from io import BytesIO
import zipfile
import json
import codecs
from math import sqrt

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.http import Http404
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.conf import settings
from django.contrib.auth import authenticate, logout, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from django.db import connection

from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin

from metro_app import filters, forms, functions, models, plots, tables

import logging

import datetime

# Get an instance of a logger.
logger = logging.getLogger(__name__)

# Thresholds for the number of centroids required for a simulation to be
# considered as having a large OD Matrix.
MATRIX_THRESHOLD = 10
# Thresholds for the number of links required for a simulation to be
# considered as having a large network (for network view).
NETWORK_THRESHOLD = 1000
# Thresholds for the number of links required for a simulation to be
# considered as having a large network (for disaggregated results).
LINK_THRESHOLD = 50000
# Maximum number of instances that can be edited at the same time in the
# object_edit view.
OBJECT_THRESHOLD = 80


# ====================
# Decorators
# ====================

def public_required(view):
    """Decorator to execute a function only if the requesting user has view
    access to the simulation.
    The decorator also converts the simulation id parameter to a Simulation
    object.
    """

    def wrap(*args, **kwargs):
        user = args[0].user  # The first arg is the request object.
        simulation_id = kwargs.pop('simulation_id')
        simulation = get_object_or_404(models.Simulation, pk=simulation_id)
        if functions.can_view(user, simulation):
            return view(*args, simulation=simulation, **kwargs)
        else:
            return HttpResponseRedirect(reverse('metro:simulation_manager'))

    return wrap


def owner_required(view):
    """Decorator to execute a function only if the requesting user has edit
    access to the simulation.
    The decorator also converts the simulation id parameter to a Simulation
    object.
    """

    def wrap(*args, **kwargs):
        user = args[0].user  # The first arg is the request object.
        simulation_id = kwargs.pop('simulation_id')
        simulation = get_object_or_404(models.Simulation, pk=simulation_id)
        if functions.can_edit(user, simulation):
            return view(*args, simulation=simulation, **kwargs)
        else:
            return HttpResponseRedirect(reverse('metro:simulation_manager'))

    return wrap


def check_demand_relation(view):
    """Decorator used in the demand views to ensure that the demand segment and
    the simulation are related.
    Without this decorator, we could view, delete or edit the user type of an
    other simulation (even private) by modifying the id in the url address.
    The decorator also converts the demand segment id to a DemandSegment
    object.
    """

    def wrap(*args, **kwargs):
        # The decorator is run after public_required or owner_required so
        # simulation_id has already been converted to a Simulation object.
        simulation = kwargs.pop('simulation')
        demandsegment_id = kwargs.pop('demandsegment_id')
        demandsegment = get_object_or_404(
            models.DemandSegment, pk=demandsegment_id)
        if simulation.scenario.demand == demandsegment.demand.first():
            return view(*args, simulation=simulation,
                        demandsegment=demandsegment)
        else:
            # The demand segment id not related to the simulation.
            return HttpResponseRedirect(reverse('metro:simulation_manager'))

    return wrap


def check_object_name(view):
    """Decorator used in the object views to ensure that the object variable is
    correctly specified.
    """

    def wrap(*args, **kwargs):
        # The decorator is run after public_required or owner_required so
        # simulation_id has already been converted to a Simulation object.
        simulation = kwargs.pop('simulation')
        object_name = kwargs.pop('object_name')
        if object_name in ('centroid', 'crossing', 'function', 'link'):
            return view(*args, simulation=simulation, object_name=object_name)
        else:
            # Invalid object name.
            raise Http404()

    return wrap


def check_run_relation(view):
    """Decorator used in the run views to ensure that the run and the
    simulation are related.
    The decorator also converts the run id to a SimulationRun object.
    """

    def wrap(*args, **kwargs):
        # The decorator is run after public_required or owner_required so
        # simulation_id has already been converted to a Simulation object.
        simulation = kwargs.pop('simulation')
        run_id = kwargs.pop('run_id')
        run = get_object_or_404(models.SimulationRun, pk=run_id)
        if run.simulation == simulation:
            return view(*args, simulation=simulation,
                        run=run)
        else:
            # The run id not related to the simulation.
            return HttpResponseRedirect(reverse('metro:simulation_manager'))

    return wrap


def check_batch_relation(view):
    """Decorator used in the batch views to ensure that the batch and the
    simulation are related.
    The decorator also converts the batch id to a Batch object.
    """

    def wrap(*args, **kwargs):
        # The decorator is run after public_required or owner_required so
        # simulation_id has already been converted to a Simulation object.
        simulation = kwargs.pop('simulation')
        batch_id = kwargs.pop('batch_id')
        batch = get_object_or_404(models.Batch, pk=batch_id)
        if batch.simulation == simulation:
            return view(*args, simulation=simulation,
                        batch=batch)
        else:
            # The run id not related to the simulation.
            return HttpResponseRedirect(reverse('metro:simulation_manager'))

    return wrap


def environment_owner_required(view):
    """Decorator to execute a function only if the requesting user has edit
    access to the environment.
    """

    def wrap(*args, **kwargs):
        user = args[0].user  # The first arg is the request object.
        environment_id = kwargs.pop('environment_id')
        environment = get_object_or_404(models.Environment, pk=environment_id)
        if functions.can_edit_environment(user, environment):
            return view(*args, environment=environment_id, **kwargs)
        else:
            return HttpResponseRedirect(reverse('metro:environments_view'))

    return wrap


def environment_can_create(view):
    """Decorator to execute a function only if the requesting user can create
    an environment.
    """

    def wrap(*args, **kwargs):
        user = args[0].user  # The first arg is the request object.

        if user.has_perm('metro_app.add_environment'):
            return view(*args, **kwargs)
        else:
            return HttpResponseRedirect(reverse('metro:simulation_manager'))

    return wrap


# ====================
# Views
# ====================

def simulation_manager(request):
    """Home page of Metropolis.
    This view shows lists of simulations and proposes a form to create a new
    simulation.
    """
    # Create lists of simulations.
    sim_user_list = models.Simulation.objects.filter(user_id=request.user.id)
    sim_public_list = models.Simulation.objects.filter(public=True)
    sim_public_list = sim_public_list.exclude(user_id=request.user.id)
    sim_pinned_list = models.Simulation.objects.filter(public=True)
    sim_pinned_list = sim_pinned_list.filter(pinned=True)
    env_list = models.Environment.objects.filter(users=request.user.id)
    simulation_env_list = []

    for env in env_list:
        sim = models.Simulation.objects.filter(environment=env)
        simulation_env_list.append((env, sim))

    sim_private_list = None
    if request.user.is_superuser:
        # Superuser can see private simulations.
        sim_private_list = models.Simulation.objects.filter(public=False)
        sim_private_list = sim_private_list.exclude(user=request.user)
    # Create a form for new simulations.
    # Added one more form for the Import Simulation Button By Shubham
    import_form = forms.SimulationImportForm(request.user)
    simulation_form = forms.BaseSimulationForm(request.user)

    # Create a form for copied simulations (the form has the same fields as the
    # form for new simulations, we add the prefix copy to differentiate the
    # two).
    copy_form = forms.BaseSimulationForm(request.user, prefix='copy')
    context = {
        'simulation_user_list': sim_user_list,
        'simulation_env_list': simulation_env_list,
        'simulation_public_list': sim_public_list,
        'simulation_pinned_list': sim_pinned_list,
        'simulation_private_list': sim_private_list,
        'simulation_form': simulation_form,
        'import_form': import_form,
        'copy_form': copy_form,
    }
    return render(request, 'metro_app/simulation_manager.html', context)


def register(request):
    """View to show the register form."""
    register_form = forms.UserCreationForm()
    return render(request, 'metro_app/register.html', {'form': register_form})


def login_view(request, login_error=False):
    """View to show the login form."""
    login_form = forms.LoginForm()
    context = {
        'form': login_form,
        'login_error': login_error,
    }
    return render(request, 'metro_app/login.html', context)


def register_action(request):
    """View triggered when an user submit a register form."""
    if request.method == 'POST':
        register_form = forms.UserCreationForm(request.POST)
        if register_form.is_valid():
            # Create a new user account.
            user = register_form.save()
            # Login the new user.
            login(request, user)
        else:
            # Return the register view with the errors.
            context = {
                'form': register_form,
                'error': register_form.errors
            }
            return render(request, 'metro_app/register.html', context)
    return HttpResponseRedirect(reverse('metro:simulation_manager'))


def login_action(request):
    """View triggered when an user login."""
    if request.method == 'POST':
        login_form = forms.LoginForm(request.POST)
        if login_form.is_valid():
            username = login_form.cleaned_data['username']
            password = login_form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                # Log the user in and redirect him to the simulation manager.
                login(request, user)
            else:
                # Authentication failed.
                return HttpResponseRedirect(
                    reverse('metro:login', kwargs={'login_error': True})
                )
        else:
            error = login_form.errors
            # If a problem occured, return to the login page and show the
            # errors.
            context = {
                'form': login_form,
                'error': error
            }
            return render(request, 'metro_app/login.html', context)
    return HttpResponseRedirect(reverse('metro:simulation_manager'))


@login_required
def logout_action(request):
    """View triggered when an user logout."""
    if request.user.is_authenticated:
        logout(request)
    return HttpResponseRedirect(reverse('metro:simulation_manager'))


class PasswordResetView(auth_views.PasswordResetView):
    template_name = 'metro_app/password_reset.html'
    email_template_name = 'metro_app/password_reset_email.html'
    success_url = reverse_lazy('metro:password_reset_done')


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'metro_app/password_reset_done.html'


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'metro_app/password_reset_confirm.html'
    success_url = reverse_lazy('metro:simulation_manager')
    post_reset_login = True


def how_to(request):
    """View with the tutorial and FAQ of Metropolis."""
    return render(request, 'metro_app/how_to.html')


def tutorial(request):
    """Simple view to send the tutorial pdf to the user."""
    try:
        file_path = (settings.BASE_DIR
                     + '/website_files/metropolis_tutorial.pdf')
        with open(file_path, 'rb') as f:
            response = HttpResponse(f, content_type='application/pdf')
            response['Content-Disposition'] = \
                'attachment; filename="how_to.pdf"'
            return response
    except FileNotFoundError:
        # Should notify an admin that the file is missing.
        raise Http404()


def osm_tutorial(request):
    """Simple view to send the osm_tutorial pdf to the user."""
    try:
        file_path = (settings.BASE_DIR
                     + '/website_files/OpenStreetMap_tutorial.pdf')
        with open(file_path, 'rb') as f:
            response = HttpResponse(f, content_type='application/pdf')
            response['Content-Disposition'] = \
                'attachment; filename="osm_tool_tutorial.pdf"'
            return response
    except FileNotFoundError:
        # Should notify an admin that the file is missing.
        raise Http404()


def contributors(request):
    """Simple view to show the people who contributed to the project."""
    return render(request, 'metro_app/contributors.html')


def disqus(request):
    """Simple view to show the disqus page."""
    return render(request, 'metro_app/disqus.html')


@require_POST
@login_required
def simulation_add_action(request):
    """This view is used when a user creates a new simulation.
    The request should contain data for the new simulation (name, comment and
    public).
    """
    # Create a form with the data send and check if it is valid.
    form = forms.BaseSimulationForm(request.user, request.POST)
    if form.is_valid():
        # Create a new simulation with the attributes sent.
        simulation = functions.create_simulation(request.user, form)
        return HttpResponseRedirect(
            reverse('metro:simulation_view', args=(simulation.id,))
        )
    else:
        # I do not see how errors could happen.
        return HttpResponseRedirect(reverse('metro:simulation_manager'))


@require_POST
@login_required
def copy_simulation(request):
    """View used to create a copy of another simulation.
    Django ORM is too slow for bulk operations on the database so we use mainly
    raw SQL query.
    To copy an object using Django, we set its primary key to None and we save
    it again.  This will generate a new id for the object. We must ensure that
    all relations between the objects remain consistent.

    For now, Policy objects are not copied.
    """
    copy_form = forms.BaseSimulationForm(
        request.user, request.POST, prefix='copy')
    if copy_form.is_valid():
        # The simulation id is hidden in an input of the pop-up (the id is
        # changed by javascript.
        simulation_id = request.POST['copy_id']
        simulation = get_object_or_404(models.Simulation, pk=simulation_id)
        # There are timeouts if the same simulation is copied twice
        # simultaneously so we wait until the simulation is unlocked.
        while simulation.locked:
            # Wait 5 seconds.
            time.sleep(5)
            simulation = get_object_or_404(models.Simulation, pk=simulation_id)
        # Lock the simulation.
        simulation.locked = True
        simulation.save()
        # Use a direct access to the database.
        with connection.cursor() as cursor:
            # Copy all the models associated with the new simulation.
            # (1) Supply.
            functionset = models.FunctionSet.objects.get(
                pk=simulation.scenario.supply.functionset.id)
            functionset.pk = None
            functionset.save()
            network = models.Network.objects.get(
                pk=simulation.scenario.supply.network.id)
            network.pk = None
            network.save()
            # (1.1) Links.
            # Find last link id right before executing the raw SQL query.
            link_last_id = models.Link.objects.last().id
            # Copy all links of the old network.
            cursor.execute(
                "INSERT INTO Link (name, destination, lanes, length, origin, "
                "speed, ul1, ul2, ul3, capacity, dynVol, dynFlo, staVol, vdf, "
                "user_id) "
                "SELECT Link.name, Link.destination, Link.lanes, "
                "Link.length, Link.origin, Link.speed, Link.ul1, Link.ul2, "
                "Link.ul3, Link.capacity, Link.dynVol, Link.dynFlo, "
                "Link.staVol, Link.vdf, Link.user_id "
                "FROM Link "
                "JOIN Network_Link "
                "ON Link.id = Network_Link.link_id "
                "WHERE Network_Link.network_id = %s;",
                [simulation.scenario.supply.network.id]
            )
            # Find id of last inserted link. It might be better to find the
            # copy of the last link of the old network in case other links
            # where added at the same time.
            new_link_last_id = models.Link.objects.last().id
            # Add the many-to-many relations between links and network.
            cursor.execute(
                "INSERT INTO Network_Link (network_id, link_id) "
                "SELECT '%s', id FROM Link WHERE id > %s and id <= %s;",
                [network.id, link_last_id, new_link_last_id]
            )
            # (1.2) Functions.
            # Find last function id.
            last_id = models.Function.objects.last().id
            # Copy all functions.
            cursor.execute(
                "INSERT INTO Function (name, expression, user_id, vdf_id) "
                "SELECT Function.name, Function.expression, Function.user_id, "
                " Function.vdf_id "
                "FROM Function JOIN FunctionSet_Function "
                "ON Function.id = FunctionSet_Function.function_id "
                "WHERE FunctionSet_Function.functionset_id = %s;",
                [simulation.scenario.supply.functionset.id]
            )
            # Find id of last inserted function.
            new_last_id = models.Function.objects.last().id
            # Add the many-to-many relations betweens functions and
            # functionset.
            cursor.execute(
                "INSERT INTO FunctionSet_Function "
                "(functionset_id, function_id) SELECT '%s', id FROM Function "
                "WHERE id > %s and id <= %s;",
                [functionset.id, last_id, new_last_id]
            )
            # Set vdf_id equal to the id of the functions.
            cursor.execute(
                "UPDATE Function "
                "JOIN FunctionSet_Function "
                "ON Function.id = FunctionSet_Function.function_id "
                "SET Function.vdf_id = Function.id "
                "WHERE FunctionSet_Function.functionset_id = %s;",
                [functionset.id]
            )
            # Create a temporary table to map old function ids with new
            # function ids.
            cursor.execute(
                "CREATE TEMPORARY TABLE function_ids "
                "(id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                "old INT, new INT);"
            )
            # Add the id of the old functions.
            cursor.execute(
                "INSERT INTO function_ids (old) "
                "SELECT Function.id "
                "FROM Function "
                "JOIN FunctionSet_Function "
                "ON Function.id = FunctionSet_Function.function_id "
                "WHERE FunctionSet_Function.functionset_id = %s;",
                [simulation.scenario.supply.functionset.id]
            )
            # Add the ids of the new functions.
            cursor.execute(
                "UPDATE function_ids, "
                "(SELECT @i:=@i+1 as row, Function.id "
                "FROM (SELECT @i:=0) AS a, Function "
                "JOIN FunctionSet_Function "
                "ON Function.id = FunctionSet_Function.function_id "
                "WHERE FunctionSet_Function.functionset_id = %s) AS src "
                "SET function_ids.new = src.id "
                "WHERE function_ids.id = src.row;",
                [functionset.id]
            )
            # Update the function of the new links using the mapping table.
            cursor.execute(
                "UPDATE Link "
                "JOIN function_ids "
                "ON Link.vdf = function_ids.old "
                "JOIN Network_Link "
                "ON Link.id = Network_Link.link_id "
                "SET Link.vdf = function_ids.new "
                "WHERE Network_Link.network_id = %s;",
                [network.id]
            )
            # (1.3) Centroids.
            # Find last centroid id.
            last_id = models.Centroid.objects.last().id
            # Copy all centroids of the old network.
            cursor.execute(
                "INSERT INTO Centroid (name, x, y, uz1, uz2, uz3, user_id) "
                "SELECT Centroid.name, Centroid.x, Centroid.y, Centroid.uz1, "
                "Centroid.uz2, Centroid.uz3, Centroid.user_id "
                "FROM Centroid "
                "JOIN Network_Centroid "
                "ON Centroid.id = Network_Centroid.centroid_id "
                "WHERE Network_Centroid.network_id = %s;",
                [simulation.scenario.supply.network.id]
            )
            # Find id of last inserted centroid.
            new_last_id = models.Centroid.objects.last().id
            # Add the many-to-many relations between centroids and network.
            cursor.execute(
                "INSERT INTO Network_Centroid (network_id, centroid_id) "
                "SELECT '%s', id FROM Centroid WHERE id > %s and id <= %s;",
                [network.id, last_id, new_last_id]
            )
            # Create a temporary table to map old centroid ids with new
            # centroid ids.
            cursor.execute(
                "CREATE TEMPORARY TABLE centroid_ids "
                "(id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                "old INT, new INT);"
            )
            # Add the id of the old centroids.
            cursor.execute(
                "INSERT INTO centroid_ids (old) "
                "SELECT Centroid.id "
                "FROM Centroid "
                "JOIN Network_Centroid "
                "ON Centroid.id = Network_Centroid.centroid_id "
                "WHERE Network_Centroid.network_id = %s;",
                [simulation.scenario.supply.network.id]
            )
            # Add the id of the old centroids.
            cursor.execute(
                "UPDATE centroid_ids, "
                "(SELECT @i:=@i+1 as row, Centroid.id "
                "FROM (SELECT @i:=0) AS a, Centroid "
                "JOIN Network_Centroid "
                "ON Centroid.id = Network_Centroid.centroid_id "
                "WHERE Network_Centroid.network_id = %s) AS src "
                "SET centroid_ids.new = src.id "
                "WHERE centroid_ids.id = src.row;",
                [network.id]
            )
            # Update the origin and destination of the new links using the
            # mapping table.
            cursor.execute(
                "UPDATE Link "
                "JOIN centroid_ids "
                "ON Link.origin = centroid_ids.old "
                "SET Link.origin = centroid_ids.new "
                "WHERE Link.id > %s AND Link.id <= %s;",
                [link_last_id, new_link_last_id]
            )
            cursor.execute(
                "UPDATE Link "
                "JOIN centroid_ids "
                "ON Link.destination = centroid_ids.old "
                "SET Link.destination = centroid_ids.new "
                "WHERE Link.id > %s AND Link.id <= %s;",
                [link_last_id, new_link_last_id]
            )
            # (1.4) Crossings.
            # Find last crossing id.
            last_id = models.Crossing.objects.last().id
            # Copy all crossings of the old network.
            cursor.execute(
                "INSERT INTO Crossing (name, x, y, un1, un2, un3, user_id) "
                "SELECT Crossing.name, Crossing.x, Crossing.y, Crossing.un1, "
                "Crossing.un2, Crossing.un3, Crossing.user_id "
                "FROM Crossing "
                "JOIN Network_Crossing "
                "ON Crossing.id = Network_Crossing.crossing_id "
                "WHERE Network_Crossing.network_id = %s;",
                [simulation.scenario.supply.network.id]
            )
            # Find id of last inserted crossing.
            new_last_id = models.Crossing.objects.last().id
            # Add the many-to-many relations between crossings and network.
            cursor.execute(
                "INSERT INTO Network_Crossing (network_id, crossing_id) "
                "SELECT '%s', id FROM Crossing WHERE id > %s and id <= %s;",
                [network.id, last_id, new_last_id]
            )
            # Create a temporary table to map old crossing ids with new
            # crossing ids.
            cursor.execute(
                "CREATE TEMPORARY TABLE crossing_ids "
                "(id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, "
                "old INT, new INT);"
            )
            # Add the id of the old crossings.
            cursor.execute(
                "INSERT INTO crossing_ids (old) "
                "SELECT Crossing.id "
                "FROM Crossing "
                "JOIN Network_Crossing "
                "ON Crossing.id = Network_Crossing.crossing_id "
                "WHERE Network_Crossing.network_id = %s;",
                [simulation.scenario.supply.network.id]
            )
            # Add the id of the old crossings.
            cursor.execute(
                "UPDATE crossing_ids, "
                "(SELECT @i:=@i+1 as row, Crossing.id "
                "FROM (SELECT @i:=0) AS a, Crossing "
                "JOIN Network_Crossing "
                "ON Crossing.id = Network_Crossing.crossing_id "
                "WHERE Network_Crossing.network_id = %s) AS src "
                "SET crossing_ids.new = src.id "
                "WHERE crossing_ids.id = src.row;",
                [network.id]
            )
            # Update the origin and destination of the new links using the
            # mapping table.
            cursor.execute(
                "UPDATE Link "
                "JOIN crossing_ids "
                "ON Link.origin = crossing_ids.old "
                "SET Link.origin = crossing_ids.new "
                "WHERE Link.id > %s AND Link.id <= %s;",
                [link_last_id, new_link_last_id]
            )
            cursor.execute(
                "UPDATE Link "
                "JOIN crossing_ids "
                "ON Link.destination = crossing_ids.old "
                "SET Link.destination = crossing_ids.new "
                "WHERE Link.id > %s AND Link.id <= %s;",
                [link_last_id, new_link_last_id]
            )
            # (1.5) Public transit.
            pttimes = models.Matrices.objects.get(
                pk=simulation.scenario.supply.pttimes.id)
            pttimes.pk = None
            pttimes.save()
            cursor.execute(
                "INSERT INTO Matrix (r, p, q, matrices_id) "
                "SELECT r, p, q, '%s' FROM Matrix "
                "WHERE matrices_id = %s;",
                [pttimes.id, simulation.scenario.supply.pttimes.id]
            )
            # Update origin and destination ids of the OD pairs.
            cursor.execute(
                "UPDATE Matrix "
                "JOIN centroid_ids "
                "ON Matrix.p = centroid_ids.old "
                "SET Matrix.p = centroid_ids.new "
                "WHERE Matrix.matrices_id = %s;",
                [pttimes.id]
            )
            cursor.execute(
                "UPDATE Matrix "
                "JOIN centroid_ids "
                "ON Matrix.q = centroid_ids.old "
                "SET Matrix.q = centroid_ids.new "
                "WHERE Matrix.matrices_id = %s;",
                [pttimes.id]
            )
            supply = models.Supply.objects.get(
                pk=simulation.scenario.supply.id)
            supply.pk = None
            supply.network = network
            supply.functionset = functionset
            supply.pttimes = pttimes
            supply.save()
            # (2) Demand.
            demand = models.Demand.objects.get(
                pk=simulation.scenario.demand.id)
            demand_segments = demand.demandsegment_set.all()
            demand.pk = None
            demand.save()
            for demand_segment in demand_segments:
                # (2.1) UserType.
                usertype = models.UserType.objects.get(
                    pk=demand_segment.usertype.id)
                usertype.pk = None
                usertype.save()
                # Copy all distributions.
                alphaTI = usertype.alphaTI
                alphaTI.pk = None
                alphaTI.save()
                usertype.alphaTI = alphaTI
                alphaTP = usertype.alphaTP
                alphaTP.pk = None
                alphaTP.save()
                usertype.alphaTP = alphaTP
                beta = usertype.beta
                beta.pk = None
                beta.save()
                usertype.beta = beta
                delta = usertype.delta
                delta.pk = None
                delta.save()
                usertype.delta = delta
                departureMu = usertype.departureMu
                departureMu.pk = None
                departureMu.save()
                usertype.departureMu = departureMu
                gamma = usertype.gamma
                gamma.pk = None
                gamma.save()
                usertype.gamma = gamma
                modeMu = usertype.modeMu
                modeMu.pk = None
                modeMu.save()
                usertype.modeMu = modeMu
                penaltyTP = usertype.penaltyTP
                penaltyTP.pk = None
                penaltyTP.save()
                usertype.penaltyTP = penaltyTP
                routeMu = usertype.routeMu
                routeMu.pk = None
                routeMu.save()
                usertype.routeMu = routeMu
                tstar = usertype.tstar
                tstar.pk = None
                tstar.save()
                usertype.tstar = tstar
                usertype.save()
                # (2.2) OD Matrix.
                matrix = models.Matrices.objects.get(
                    pk=demand_segment.matrix.id)
                matrix.pk = None
                matrix.save()
                # (2.3) OD Matrix pairs.
                # Copy all OD pairs and change the Matrix foreign key.
                cursor.execute(
                    "INSERT INTO Matrix (r, p, q, matrices_id) "
                    "SELECT r, p, q, '%s' FROM Matrix "
                    "WHERE matrices_id = %s;",
                    [matrix.id, demand_segment.matrix.id]
                )
                # Update origin and destination ids of the OD pairs.
                cursor.execute(
                    "UPDATE Matrix "
                    "JOIN centroid_ids "
                    "ON Matrix.p = centroid_ids.old "
                    "SET Matrix.p = centroid_ids.new "
                    "WHERE Matrix.matrices_id = %s;",
                    [matrix.id]
                )
                cursor.execute(
                    "UPDATE Matrix "
                    "JOIN centroid_ids "
                    "ON Matrix.q = centroid_ids.old "
                    "SET Matrix.q = centroid_ids.new "
                    "WHERE Matrix.matrices_id = %s;",
                    [matrix.id]
                )
                # (2.4) Demand Segment.
                demand_segment.pk = None
                demand_segment.usertype = usertype
                demand_segment.matrix = matrix
                demand_segment.save()
                # (2.5) Add the relations.
                demand_segment.demand.clear()
                demand_segment.demand.add(demand)
            # (3) Scenario.
            scenario = models.Scenario.objects.get(pk=simulation.scenario.id)
            scenario.pk = None
            scenario.supply = supply
            scenario.demand = demand
            scenario.save()
            # Unlock the simulation before copying it.
            simulation.locked = False
            simulation.save()
            # (4) Simulation.
            simulation.pk = None
            simulation.scenario = scenario
            simulation.user = request.user
            simulation.name = copy_form.cleaned_data['name']
            simulation.comment = copy_form.cleaned_data['comment']
            simulation.public = copy_form.cleaned_data['public']
            simulation.pinned = False
            # Here, we could copy the json file of the copied simulation if the
            # copied simulation has not changed. For now, I only put
            # has_changed to True for the new simulation so that a new json
            # file will be generated.
            simulation.has_changed = True
            simulation.save()
        return HttpResponseRedirect(
            reverse('metro:simulation_view', args=(simulation.id,))
        )
    return HttpResponseRedirect(reverse('metro:simulation_manager'))


@owner_required
def simulation_delete(request, simulation):
    """View used to delete a simulation.

    The view deletes the Simulation object and all objects associated with it.
    """
    models.SimulationMOEs.objects.filter(simulation=simulation.id).delete()
    network = simulation.scenario.supply.network
    functionset = simulation.scenario.supply.functionset
    demand = simulation.scenario.demand
    network.delete()
    functionset.delete()
    demand.delete()
    return HttpResponseRedirect(reverse('metro:simulation_manager'))


@public_required
def simulation_view(request, simulation):
    """Main view of a simulation."""
    # Some elements are only displayed if the user owns the simulation.
    owner = functions.can_edit(request.user, simulation)
    # Create the form to copy the simulation.
    copy_form = forms.BaseSimulationForm(request.user, prefix='copy')
    # Create the form to edit name, comment and public.
    edit_form = forms.BaseSimulationForm(request.user, instance=simulation)
    # Create the form to edit the parameters.
    simulation_form = forms.ParametersSimulationForm(
        owner=owner, instance=simulation)
    # Count the number of each elements in the network.
    network = dict()
    network['centroids'] = functions.get_query('centroid', simulation).count()
    network['crossings'] = functions.get_query('crossing', simulation).count()
    network['links'] = functions.get_query('link', simulation).count()
    network['functions'] = functions.get_query('function', simulation).count()
    # File where the data for the network are stored.
    output_file = (
        '{0}/website_files/network_output/network_{1!s}.json'
    ).format(settings.BASE_DIR, simulation.id)
    network['generated'] = (os.path.isfile(output_file)
                            and not simulation.has_changed)
    # Count the number of user types.
    travelers = dict()
    travelers['type'] = functions.get_query('usertype', simulation).count()
    # Count the number of travelers
    matrices = functions.get_query('matrices', simulation)
    nb_travelers = matrices.aggregate(Sum('total'))['total__sum']
    if nb_travelers is None:
        nb_travelers = 0
    else:
        nb_travelers = int(nb_travelers)
    travelers['nb_travelers'] = nb_travelers
    # Count the number of policies.
    policy = dict()
    policy['count'] = functions.get_query('policy', simulation).count()
    # Count the number of runs.
    simulation_runs = functions.get_query('run', simulation)
    runs = dict()
    runs['nb_run'] = simulation_runs.count()
    # Check if a run is in progress.
    run_in_progress = simulation_runs.filter(status__in=('Preparing',
                                                         'Running',
                                                         'Ending'))
    runs['in_progress'] = run_in_progress.exists()
    if runs['in_progress']:
        runs['last'] = run_in_progress.last()
    # Check if the simulation can be run (there are a network and travelers).
    complete_network = (network['centroids'] > 1
                        and network['crossings'] > 0
                        and network['links'] > 0
                        and network['functions'] > 0)
    complete_simulation = complete_network and travelers['nb_travelers'] > 0
    # Check if there is a public transit network (in case modal choice is
    # enabled).
    good_pt = True
    if not functions.get_query('public_transit', simulation).exists():
        usertypes = functions.get_query('usertype', simulation)
        modal_choice = False
        for usertype in usertypes:
            if usertype.modeChoice == 'true':
                modal_choice = True
        if modal_choice:
            good_pt = False
    # Create a form to run the simulation.
    run_form = None
    if owner and complete_simulation:
        run_form = forms.RunForm(
            initial={'name': 'Run {}'.format(runs['nb_run'] + 1)})
    # Create a form to run a batch.
    nb_batch = functions.get_query('batch', simulation).count()
    batch_form = forms.BatchForm(
        initial={'name': 'Batch {}'.format(nb_batch+1)})
    # Check if the simulation has any batch.
    has_batch = nb_batch > 0
    context = {
        'simulation': simulation,
        'owner': owner,
        'copy_form': copy_form,
        'edit_form': edit_form,
        'simulation_form': simulation_form,
        'network': network,
        'travelers': travelers,
        'policy': policy,
        'runs': runs,
        'complete_network': complete_network,
        'complete_simulation': complete_simulation,
        'good_pt': good_pt,
        'run_form': run_form,
        'batch_form': batch_form,
        'has_batch': has_batch,
    }
    return render(request, 'metro_app/simulation_view.html', context)


@require_POST
@owner_required
def simulation_view_save(request, simulation):
    """View to save the changes to the simulation parameters."""
    simulation_form = forms.ParametersSimulationForm(
        owner=True, data=request.POST, instance=simulation)
    if simulation_form.is_valid():
        simulation_form.save()
        # Variables stac_check and iterations_check are not used by Metropolis
        # so if the variable is not checked, we must put the associated
        # variable to 0.
        if not simulation.stac_check:
            simulation.stacLim = 0
            simulation.save()
        if not simulation.iterations_check:
            simulation.iterations = 0
            simulation.save()
        return HttpResponseRedirect(
            reverse('metro:simulation_view',
                    args=(simulation.id,))
        )
    else:
        # Redirect to a page with the errors (should not happen).
        context = {
            'simulation': simulation,
            'form': simulation_form,
        }
        return render(request, 'metro_app/errors.html', context)


@require_POST
@owner_required
def simulation_view_edit(request, simulation):
    """View to save the modification to the name, comment and status of the
    simulation.
    """
    edit_form = forms.BaseSimulationForm(
        request.user, data=request.POST, instance=simulation)
    if edit_form.is_valid():
        edit_form.save()
        return HttpResponseRedirect(
            reverse('metro:simulation_view',
                    args=(simulation.id,))
        )
    else:
        # Redirect to a page with the errors (should not happen).
        context = {
            'simulation': simulation,
            'form': edit_form,
        }
        return render(request, 'metro_app/errors.html', context)


@public_required
def demand_view(request, simulation):
    """Main view to list and edit the user types."""
    demandsegments = functions.get_query('demandsegment', simulation)
    owner = functions.can_edit(request.user, simulation)
    # The matrix cannot be edit if the number of centroids is too large.
    nb_centroids = functions.get_query('centroid', simulation).count()
    large_matrix = nb_centroids > MATRIX_THRESHOLD
    # The matrix is empty if there is no centroid.
    has_centroid = nb_centroids > 0
    # Create a form to import OD matrices.
    import_form = forms.ImportForm()
    context = {
        'simulation': simulation,
        'demandsegments': demandsegments,
        'owner': owner,
        'large_matrix': large_matrix,
        'has_centroid': has_centroid,
        'import_form': import_form,
    }
    return render(request, 'metro_app/demand_view.html', context)


@owner_required
def usertype_add(request, simulation):
    """Add a new user type and initiate its distributions with default values.
    """
    # Create new distributions with good defaults.
    alphaTI = models.Distribution(type='NONE', mean=10)
    alphaTP = models.Distribution(type='NONE', mean=15)
    beta = models.Distribution(type='NONE', mean=5)
    delta = models.Distribution(type='NONE', mean=10)
    departureMu = models.Distribution(type='NONE', mean=2)
    gamma = models.Distribution(type='NONE', mean=20)
    modeMu = models.Distribution(type='NONE', mean=5)
    penaltyTP = models.Distribution(type='NONE', mean=2)
    routeMu = models.Distribution(type='NONE', mean=10)
    # Default value for t star is average arrival at middle of period and
    # uniform distribution over half of the period.
    mid_time = (simulation.startTime + simulation.lastRecord) / 2
    length = simulation.lastRecord - simulation.startTime
    tstar = models.Distribution(
        type='UNIFORM', mean=mid_time, std=length / (4 * sqrt(3)))
    # Save the distributions to generate ids.
    alphaTI.save()
    alphaTP.save()
    beta.save()
    delta.save()
    departureMu.save()
    gamma.save()
    modeMu.save()
    penaltyTP.save()
    routeMu.save()
    tstar.save()
    # Create the new user type.
    usertype = models.UserType()
    usertype.alphaTI = alphaTI
    usertype.alphaTP = alphaTP
    usertype.beta = beta
    usertype.delta = delta
    usertype.departureMu = departureMu
    usertype.gamma = gamma
    usertype.modeMu = modeMu
    usertype.penaltyTP = penaltyTP
    usertype.routeMu = routeMu
    usertype.tstar = tstar
    # Set user_id to user_id of previous usertype + 1.
    usertypes = functions.get_query('usertype', simulation)
    if usertypes.exists():
        usertype.user_id = usertypes.last().user_id + 1
    else:
        usertype.user_id = 1
    usertype.save()
    # Create a demand segment and a matrix for the user type.
    matrix = models.Matrices()
    matrix.save()
    demandsegment = models.DemandSegment()
    demandsegment.usertype = usertype
    demandsegment.matrix = matrix
    demandsegment.save()
    demandsegment.demand.add(simulation.scenario.demand)
    # Return the view to edit the new user type.
    return HttpResponseRedirect(
        reverse('metro:usertype_edit', args=(simulation.id, demandsegment.id,))
    )


@owner_required
@check_demand_relation
def usertype_edit(request, simulation, demandsegment):
    """View to edit the parameters of an user type."""
    form = forms.UserTypeForm(instance=demandsegment.usertype)
    context = {
        'simulation': simulation,
        'demandsegment': demandsegment,
        'form': form,
    }
    return render(request, 'metro_app/usertype_edit.html', context)


@require_POST
@owner_required
@check_demand_relation
def usertype_edit_save(request, simulation, demandsegment):
    """Save the parameters of an user type."""
    scale = demandsegment.scale
    form = forms.UserTypeForm(
        data=request.POST, instance=demandsegment.usertype)
    if form.is_valid():
        form.save()
        demandsegment.refresh_from_db()
        # Check if value of scale has changed.
        if demandsegment.scale != scale:
            # Update total population.
            matrix = demandsegment.matrix
            matrix_points = models.Matrix.objects.filter(matrices=matrix)
            if matrix_points.exists():
                # It is not necessary to compute total population if the O-D
                # matrix is empty.
                matrix.total = (demandsegment.scale
                                * matrix_points.aggregate(Sum('r'))['r__sum'])
                matrix.save()
                simulation.has_changed = True
                simulation.save()
        return HttpResponseRedirect(
            reverse('metro:demand_view',
                    args=(simulation.id,))
        )
    else:
        # Redirect to a page with the errors (should not happen).
        context = {
            'simulation': simulation,
            'form': form,
        }
        return render(request, 'metro_app/errors.html', context)


@owner_required
@check_demand_relation
def usertype_delete(request, simulation, demandsegment):
    """Delete an user type and all related objects."""
    # With CASCADE attribute, everything should be delete (demand segment, user
    # type, distributions, matrix and matrix points).
    demandsegment.delete()
    simulation.has_changed = True
    simulation.save()
    return HttpResponseRedirect(
        reverse('metro:demand_view', args=(simulation.id,))
    )


@public_required
@check_demand_relation
def usertype_view(request, simulation, demandsegment):
    """View the parameters of an user type."""
    context = {
        'simulation': simulation,
        'usertype': demandsegment.usertype,
        'demandsegment': demandsegment,
    }
    return render(request, 'metro_app/usertype_view.html', context)


@public_required
@check_demand_relation
def matrix_main(request, simulation, demandsegment):
    """View to display the OD Matrix main page of an user type."""
    # Get matrix.
    matrix = demandsegment.matrix
    # Get total population.
    total = matrix.total
    # Get centroids.
    centroids = functions.get_query('centroid', simulation)
    has_centroid = centroids.count() >= 2
    large_matrix = centroids.count() > MATRIX_THRESHOLD
    # Get an import form.
    import_form = forms.ImportForm()
    # Check ownership.
    owner = functions.can_edit(request.user, simulation)
    context = {
        'simulation': simulation,
        'demandsegment': demandsegment,
        'total': total,
        'has_centroid': has_centroid,
        'large_matrix': large_matrix,
        'import_form': import_form,
        'owner': owner,
    }
    return render(request, 'metro_app/matrix_main.html', context)


@public_required
@check_demand_relation
def matrix_view(request, simulation, demandsegment):
    """View to display the OD Matrix of an user type."""
    centroids = functions.get_query('centroid', simulation)
    if centroids.count() > MATRIX_THRESHOLD:
        # Large matrix, return a table instead.
        return MatrixListView.as_view()(request, simulation=simulation,
                                        demandsegment=demandsegment)
    else:
        # Small matrix, return it.
        matrix = demandsegment.matrix
        matrix_points = models.Matrix.objects.filter(matrices=matrix)
        od_matrix = []
        # For each row, we build an array which will be appended to the
        # od_matrix array.
        # The row array has the origin centroid as first value.
        # The subsequent values are the population value of the od pairs.
        # For od pair with identical origin and destination, we append -1 to
        # the row array.
        for row_centroid in centroids:
            row = [row_centroid]
            for column_centroid in centroids:
                if row_centroid == column_centroid:
                    row.append(-1)
                else:
                    try:
                        couple_object = matrix_points.get(
                            p=row_centroid,
                            q=column_centroid,
                            matrices=matrix
                        )
                        row.append(couple_object.r)
                    except models.Matrix.DoesNotExist:
                        row.append(0)
            od_matrix.append(row)
        # Get total population.
        total = matrix.total
        context = {
            'simulation': simulation,
            'demandsegment': demandsegment,
            'centroids': centroids,
            'od_matrix': od_matrix,
            'total': total,
        }
        return render(request, 'metro_app/matrix_view.html', context)


@owner_required
@check_demand_relation
def matrix_edit(request, simulation, demandsegment):
    """View to edit the OD Matrix of an user type."""
    # Get some objects.
    matrix = demandsegment.matrix
    matrix_points = models.Matrix.objects.filter(matrices=matrix)
    centroids = functions.get_query('centroid', simulation)
    od_matrix = []
    # For each row, we build an array which will be appended to the od_matrix
    # array.
    # The row array has the origin centroid as first value.
    # The subsequent values are tuples with the id of the od pair, the
    # population value of the od pair and the index of the form (used by django
    # to save the formset).
    # For od pair with identical origin and destination, we append 0 to the row
    # array.
    i = 0
    for row_centroid in centroids:
        row = [row_centroid]
        for column_centroid in centroids:
            if row_centroid == column_centroid:
                row.append(0)
            else:
                couple_object, created = matrix_points.get_or_create(
                    p=row_centroid,
                    q=column_centroid,
                    matrices=matrix
                )
                row.append((couple_object.id, couple_object.r, i))
                i += 1
        od_matrix.append(row)
    # Create a formset to obtain the management form.
    formset = forms.MatrixFormSet(
        queryset=models.Matrix.objects.filter(matrices=matrix),
    )
    # Get total population.
    total = int(matrix.total)
    context = {
        'simulation': simulation,
        'centroids': centroids,
        'demandsegment': demandsegment,
        'od_matrix': od_matrix,
        'formset': formset,
        'total': total
    }
    return render(request, 'metro_app/matrix_edit.html', context)


@require_POST
@owner_required
@check_demand_relation
def matrix_save(request, simulation, demandsegment):
    """View to save the OD Matrix of an user type."""
    matrix = demandsegment.matrix
    # Get the formset from the POST data and save it.
    formset = forms.MatrixFormSet(request.POST)
    if formset.is_valid():
        formset.save()
        # Update total.
        matrix_points = models.Matrix.objects.filter(matrices=matrix)
        matrix.total = \
            demandsegment.scale * matrix_points.aggregate(Sum('r'))['r__sum']
        matrix.save()
        simulation.has_changed = True
        simulation.save()
    else:
        # Redirect to a page with the errors.
        context = {
            'simulation': simulation,
            'form': formset,
        }
        return render(request, 'metro_app/errors.html', context)
    return HttpResponseRedirect(reverse(
        'metro:matrix_edit', args=(simulation.id, demandsegment.id,)
    ))


@public_required
@check_demand_relation
def matrix_export(request, simulation, demandsegment):
    """View to send a file with the OD Matrix to the user."""
    dir_name = functions.get_export_directory()
    filename = functions.matrix_export_function(
        simulation, demandsegment, dir_name)
    if filename is None:
        return Http404()
    with codecs.open(filename, 'r', encoding='utf8') as f:
        # Build a response to send a file.
        response = HttpResponse(f.read())
        response['content_type'] = 'text/tab-separated-values'
        name = 'matrix_{}.tsv'.format(demandsegment.usertype.user_id)
        response['Content-Disposition'] = \
            'attachement; filename={}'.format(name)
    # We delete the export directory to save disk space.
    shutil.rmtree(dir_name, ignore_errors=True)
    return response


@require_POST
@owner_required
@check_demand_relation
def matrix_import(request, simulation, demandsegment):
    """View to convert the imported file to an O-D matrix in the database."""
    try:
        encoded_file = request.FILES['import_file']
        functions.matrix_import_function(
            encoded_file, simulation, demandsegment)
    except Exception as e:
        print(e)
        context = {
            'simulation': simulation,
            'object': 'matrix',
        }
        return render(request, 'metro_app/import_error.html', context)
    else:
        return HttpResponseRedirect(reverse(
            'metro:matrix_view', args=(simulation.id, demandsegment.id,)
        ))


@owner_required
@check_demand_relation
def matrix_reset(request, simulation, demandsegment):
    """View to reset all OD pairs of an O-D matrix."""
    # Get matrix.
    matrix = demandsegment.matrix
    # Delete matrix points.
    matrix_points = models.Matrix.objects.filter(matrices=matrix)
    matrix_points.delete()
    # Update total.
    matrix.total = 0
    matrix.save()
    return HttpResponseRedirect(reverse(
        'metro:matrix_main', args=(simulation.id, demandsegment.id,)
    ))


@public_required
def pricing_main(request, simulation):
    """View to display the road pricing main page of an user type."""
    # Get number of tolls.
    policies = functions.get_query('policy', simulation)
    tolls = policies.filter(type='PRICING')
    count = tolls.count()
    # Get links.
    links = functions.get_query('link', simulation)
    has_link = links.count() >= 1
    # Get an import form.
    import_form = forms.ImportForm()
    # Check ownership.
    owner = functions.can_edit(request.user, simulation)
    context = {
        'simulation': simulation,
        'count': count,
        'has_link': has_link,
        'import_form': import_form,
        'owner': owner,
    }
    return render(request, 'metro_app/pricing_main.html', context)


@public_required
def pricing_view(request, simulation):
    """View to display the tolls of an user type."""
    return TollListView.as_view()(request, simulation=simulation, )


@owner_required
def pricing_edit(request, simulation):
    """View to edit the tolls."""
    policies = functions.get_query('policy', simulation)
    tolls = policies.filter(type='PRICING')
    # Get all links of the network.
    links = functions.get_query('link', simulation)
    # Get all LinkSelection of the network.
    locations = models.LinkSelection.objects.filter(
        network=simulation.scenario.supply.network
    )
    # Create a formset to edit the objects.
    formset = forms.PolicyFormSet
    context = {
        'simulation': simulation,
        'tolls': tolls,
        'links': links,
        'locations': locations,
        'formset': formset,
    }
    return render(request, 'metro_app/pricing_edit.html', context)


@require_POST
@owner_required
def pricing_save(request, simulation):
    """View to save the tolls of an user type."""
    # Retrieve the formset from the POST data.
    formset = forms.PolicyFormSet(request.POST)
    if formset.is_valid():
        # Save the formset (updated values and newly created objects).
        formset.save()
        simulation.has_changed = True
        simulation.save()
    else:
        # Redirect to a page with the errors.
        context = {
            'simulation': simulation,
            'form': formset,
        }
        return render(request, 'metro_app/errors.html', context)

    return HttpResponseRedirect(reverse(
        'metro:pricing_edit', args=(simulation.id,)
    ))


@public_required
def pricing_export(request, simulation):
    """View to send a file with the tolls of an user type."""
    dir_name = functions.get_export_directory()
    filename = functions.pricing_export_function(simulation, dir_name)
    if filename is None:
        return Http404()
    with codecs.open(filename, 'r', encoding='utf8') as f:
        # Build a response to send a file.
        response = HttpResponse(f.read())
        response['content_type'] = 'text/tab-separated-values'
        response['Content-Disposition'] = 'attachement; filename=pricings.tsv'
    # We delete the export directory to save disk space.
    shutil.rmtree(dir_name, ignore_errors=True)
    return response


@require_POST
@owner_required
def pricing_import(request, simulation):
    """View to convert the imported file to tolls in the database."""
    try:
        encoded_file = request.FILES['import_file']
        functions.pricing_import_function(encoded_file, simulation)
    except Exception as e:
        # Catch any exception while importing the file and return an error page
        # if there is any.
        print(e)
        context = {
            'simulation': simulation,
            'object': 'pricing',
        }
        return render(request, 'metro_app/import_error.html', context)
    else:
        return HttpResponseRedirect(reverse(
            'metro:pricing_main', args=(simulation.id,)
        ))


@owner_required
def pricing_reset(request, simulation):
    """View to reset the tolls of an user type."""
    # Get all tolls.
    policies = functions.get_query('policy', simulation)
    tolls = policies.filter(type='PRICING')
    # Delete the Policy objects (the LinkSelection objects are not deleted).
    tolls.delete()
    return HttpResponseRedirect(reverse(
        'metro:pricing_main', args=(simulation.id,)
    ))


@public_required
def public_transit_view(request, simulation):
    """Main view of the public transit system."""
    owner = functions.can_edit(request.user, simulation)
    centroids = functions.get_query('centroid', simulation)
    has_centroid = centroids.exists()
    large_matrix = False
    if has_centroid:
        large_matrix = centroids.count() > MATRIX_THRESHOLD
    public_transit_pairs = functions.get_query('public_transit', simulation)
    is_empty = not public_transit_pairs.exists()
    is_complete = False
    if not is_empty:
        # Public transit system is complete if there is the travel time for all
        # O-D pairs.
        nb_centroids = centroids.count()
        nb_pairs = public_transit_pairs.count()
        is_complete = nb_pairs >= nb_centroids * (nb_centroids - 1)
    import_form = forms.ImportForm()
    context = {
        'simulation': simulation,
        'owner': owner,
        'is_empty': is_empty,
        'is_complete': is_complete,
        'import_form': import_form,
        'has_centroid': has_centroid,
        'large_matrix': large_matrix,
    }
    return render(request, 'metro_app/public_transit_view.html', context)


@public_required
def public_transit_list(request, simulation):
    """View to display the public-transit travel times."""
    centroids = functions.get_query('centroid', simulation)
    if centroids.count() > MATRIX_THRESHOLD:
        # Large matrix, return a table instead.
        return PTMatrixListView.as_view()(request, simulation=simulation)
    else:
        # Small matrix, return it.
        matrix_points = functions.get_query('public_transit', simulation)
        od_matrix = []
        # For each row, we build an array which will be appended to the
        # od_matrix array.
        # The row array has the origin centroid as first value.
        # The subsequent values are the population value of the od pairs.
        # For od pair with identical origin and destination, we append -1 to
        # the row array.
        for row_centroid in centroids:
            row = [row_centroid]
            for column_centroid in centroids:
                if row_centroid == column_centroid:
                    row.append(-1)
                else:
                    try:
                        couple_object = matrix_points.get(
                            p=row_centroid,
                            q=column_centroid,
                        )
                        row.append(couple_object.r)
                    except models.Matrix.DoesNotExist:
                        row.append(0)
            od_matrix.append(row)
        demandsegment = functions.get_query('demandsegment', simulation)
        context = {
            'simulation': simulation,
            'demandsegment': demandsegment,
            'centroids': centroids,
            'od_matrix': od_matrix,
            'public_transit': True,
        }
        return render(request, 'metro_app/matrix_view.html', context)


@owner_required
def public_transit_edit(request, simulation):
    """View to edit the public transit OD Matrix."""
    matrix = simulation.scenario.supply.pttimes
    matrix_points = functions.get_query('public_transit', simulation)
    centroids = functions.get_query('centroid', simulation)
    od_matrix = []
    # For each row, we build an array which will be appended to the od_matrix
    # array.
    # The row array has the origin centroid as first value.
    # The subsequent values are tuples with the id of the od pair, the
    # population value of the od pair and the index of the form (used by django
    # to save the formset).
    # For od pair with identical origin and destination, we append 0 to the row
    # array.
    i = 0
    for row_centroid in centroids:
        row = [row_centroid]
        for column_centroid in centroids:
            if row_centroid == column_centroid:
                row.append(0)
            else:
                # There is a problem here. I create empty OD pairs with value 0
                # so that it is possible to edit all cells of the matrix.
                # However, the pairs stay in the database when the formset is
                # set. Therefore, the website with think that the public
                # transit system is complete even if all values are 0 (see
                # public_transit_view).
                couple_object, created = matrix_points.get_or_create(
                    p=row_centroid,
                    q=column_centroid,
                    matrices=matrix
                )
                row.append((couple_object.id, couple_object.r, i))
                i += 1
        od_matrix.append(row)
    # Create a formset to obtain the management form.
    formset = forms.MatrixFormSet(queryset=matrix_points.all())
    context = {
        'simulation': simulation,
        'centroids': centroids,
        'od_matrix': od_matrix,
        'formset': formset,
        'public_transit': True,
    }
    return render(request, 'metro_app/matrix_edit.html', context)


@require_POST
@owner_required
def public_transit_edit_save(request, simulation):
    """View to save the public transit OD Matrix."""
    # Get the formset from the POST data and save it.
    formset = forms.MatrixFormSet(request.POST)
    if formset.is_valid():
        formset.save()
    else:
        # Redirect to a page with the errors.
        context = {
            'simulation': simulation,
            'form': formset,
        }
        return render(request, 'metro_app/errors.html', context)
    return HttpResponseRedirect(reverse(
        'metro:public_transit_edit', args=(simulation.id,)
    ))


@owner_required
def public_transit_delete(request, simulation):
    """Delete all OD pairs of the public transit OD matrix.
    The Matrices object is not deleted so that the user can add OD pairs again.
    """
    od_pairs = functions.get_query('public_transit', simulation)
    od_pairs.delete()
    return HttpResponseRedirect(reverse(
        'metro:public_transit_view', args=(simulation.id,)
    ))


@require_POST
@owner_required
def public_transit_import(request, simulation):
    """View to convert the imported file to a public transit matrix in the
    database."""
    try:
        encoded_file = request.FILES['import_file']
        functions.public_transit_import_function(encoded_file, simulation)
    except Exception as e:
        print(e)
        context = {
            'simulation': simulation,
            'object': 'public_transit',
        }
        return render(request, 'metro_app/import_error.html', context)
    else:
        return HttpResponseRedirect(reverse(
            'metro:public_transit_view', args=(simulation.id,)
        ))


@public_required
def public_transit_export(request, simulation):
    """View to send a file with the public transit OD Matrix to the user."""
    dir_name = functions.get_export_directory()
    filename = functions.public_transit_export_function(simulation, dir_name)
    if filename is None:
        return Http404()
    with codecs.open(filename, 'r', encoding='utf8') as f:
        # Build a response to send a file.
        response = HttpResponse(f.read())
        response['content_type'] = 'text/tab-separated-values'
        response['Content-Disposition'] = \
            'attachement; filename=public_transit.tsv'
    # We delete the export directory to save disk space.
    shutil.rmtree(dir_name, ignore_errors=True)
    return response


@public_required
@check_object_name
def object_view(request, simulation, object_name):
    """Main view of a network object."""
    owner = functions.can_edit(request.user, simulation)
    query = functions.get_query(object_name, simulation)
    large_count = query.count() > OBJECT_THRESHOLD
    network_empty = False
    if object_name == 'link':
        # Allow the user to edit links only if there are at least two
        # centroids, one crossing and one congestion function.
        nb_centroids = functions.get_query('centroid', simulation).count()
        nb_crossings = functions.get_query('crossing', simulation).count()
        nb_functions = functions.get_query('function', simulation).count()
        network_empty = not (nb_centroids >= 2 and nb_crossings >= 1
                             and nb_functions >= 1)
    import_form = forms.ImportForm()
    context = {
        'simulation': simulation,
        'owner': owner,
        'count': query.count(),
        'object': object_name,
        'large_count': large_count,
        'network_empty': network_empty,
        'import_form': import_form,
    }
    return render(request, 'metro_app/object_view.html', context)


@public_required
@check_object_name
def object_list(request, simulation, object_name):
    """View to list all instances of a network object."""
    if object_name == 'centroid':
        return CentroidListView.as_view()(request, simulation=simulation)
    elif object_name == 'crossing':
        return CrossingListView.as_view()(request, simulation=simulation)
    elif object_name == 'link':
        return LinkListView.as_view()(request, simulation=simulation)
    elif object_name == 'function':
        return FunctionListView.as_view()(request, simulation=simulation)


@owner_required
@check_object_name
def object_edit(request, simulation, object_name):
    """View to edit all instances of a network object."""
    # Object is either 'centroid', 'crossing', 'link' or 'function'.
    # Create a formset to edit the objects.
    formset = gen_formset(object_name, simulation)
    context = {
        'simulation': simulation,
        'object': object_name,
        'formset': formset,
    }
    return render(request, 'metro_app/object_edit.html', context)


@require_POST
@owner_required
@check_object_name
def object_edit_save(request, simulation, object_name):
    """View to save the edited network objects."""
    # Retrieve the formset from the POST data.
    formset = gen_formset(object_name, simulation, request=request)
    if formset.is_valid():
        # Save the formset (updated values and newly created objects).
        formset.save()
        # Update the foreign keys (we cannot select the newly added forms so we
        # do it for all forms not deleted).
        changed_forms = list(
            set(formset.forms) - set(formset.deleted_forms)
        )
        if object_name in ['centroid', 'crossing', 'link']:
            for form in changed_forms:
                # Link the object to the correct network.
                form.instance.network.add(
                    simulation.scenario.supply.network
                )
        elif object_name == 'function':
            for form in changed_forms:
                # Link the function to the correct functionset.
                form.vdf_id = form.instance.id
                form.save()
                form.instance.functionset.add(
                    simulation.scenario.supply.functionset
                )
        simulation.has_changed = True
        simulation.save()
        return HttpResponseRedirect(reverse(
            'metro:object_edit', args=(simulation.id, object_name,)
        ))
    else:
        # Redirect to a page with the errors.
        context = {
            'simulation': simulation,
            'formset': formset,
        }
        return render(request, 'metro_app/errors_formset.html', context)


@require_POST
@owner_required
@check_object_name
def object_import(request, simulation, object_name):
    """View to import instances of a network object."""
    encoded_file = request.FILES['import_file']
    try:
        functions.object_import_function(encoded_file, simulation, object_name)
    except Exception as e:
        print(e)
        context = {
            'simulation': simulation,
            'object': object_name,
        }
        return render(request, 'metro_app/import_error.html', context)
    else:
        return HttpResponseRedirect(
            reverse('metro:object_list', args=(simulation.id, object_name,))
        )


@public_required
@check_object_name
def object_export(request, simulation, object_name):
    """View to export all instances of a network object."""
    dir_name = functions.get_export_directory()
    filename = functions.object_export_function(
        simulation, object_name, dir_name)
    if filename is None:
        return Http404()
    with codecs.open(filename, 'r', encoding='utf8') as f:
        # Build a response to send a file.
        response = HttpResponse(f.read())
        response['content_type'] = 'text/tab-separated-values'
        name = functions.metro_to_user(object_name).replace(' ', '_')
        response['Content-Disposition'] = \
            'attachement; filename={}s.tsv'.format(name)
    # We delete the export directory to save disk space.
    shutil.rmtree(dir_name, ignore_errors=True)
    return response


@owner_required
@check_object_name
def object_delete(request, simulation, object_name):
    """View to delete all instances of a network objects."""
    query = functions.get_query(object_name, simulation)
    if object_name in ('centroid', 'crossing'):
        # Django cannot manage well delete for these objects.
        name = 'Centroid' if object_name == 'centroid' else 'Crossing'
        ids = query.values_list('id', flat=True)
        str_ids = ','.join([str(x) for x in ids])
        with connection.cursor() as cursor:
            if object_name == 'centroid':
                cursor.execute(
                    "DELETE FROM Matrix WHERE p IN ({});".format(str_ids)
                )
                cursor.execute(
                    "DELETE FROM Matrix WHERE q IN ({});".format(str_ids)
                )
            cursor.execute(
                "DELETE FROM Network_{} "
                "WHERE {}_id IN ({});".format(name, object_name, str_ids)
            )
            cursor.execute(
                "DELETE Network_Link "
                "FROM Network_Link JOIN Link "
                "ON Network_Link.link_id = Link.id "
                "WHERE Link.origin IN ({});".format(str_ids)
            )
            cursor.execute(
                "DELETE Network_Link "
                "FROM Network_Link JOIN Link "
                "ON Network_Link.link_id = Link.id "
                "WHERE Link.destination IN ({});".format(str_ids)
            )
            cursor.execute(
                "DELETE FROM {} WHERE id IN ({});".format(name, str_ids)
            )
            cursor.execute(
                "DELETE FROM Link WHERE origin IN ({});".format(str_ids)
            )
            cursor.execute(
                "DELETE FROM Link WHERE destination IN ({});".format(str_ids)
            )
        if object_name == 'centroid':
            # Reset the number of travelers.
            matrices = functions.get_query('matrices', simulation)
            for matrix in matrices:
                matrix.total = 0
                matrix.save()
    else:
        # Let Django do the job.
        query.delete()
    simulation.has_changed = True
    simulation.save()
    return HttpResponseRedirect(reverse(
        'metro:object_view', args=(simulation.id, object_name,)
    ))


@require_POST
@owner_required
def simulation_run_action(request, simulation):
    """View to create a new SimulationRun and launch the simulation."""
    # Check that there is no run in progress for this simulation.
    running_simulations = models.SimulationRun.objects.filter(
        simulation=simulation
    ).filter(status__in=('Preparing', 'Running', 'Ending'))
    if not running_simulations.exists():
        # Create a SimulationRun object to keep track of the run.
        run_form = forms.RunForm(request.POST)
        if run_form.is_valid():
            run = run_form.save(simulation)
            functions.run_simulation(run)
        return HttpResponseRedirect(
            reverse('metro:simulation_run_view', args=(simulation.id, run.id,))
        )
    return HttpResponseRedirect(reverse(
        'metro:simulation_run_list', args=(simulation.id,)
    ))


@owner_required
@check_run_relation
def simulation_run_stop(request, simulation, run):
    """View to stop a running simulation."""
    if run.status == 'Running':
        # Create the stop file.
        # The simulation will stop at the end of the current iteration.
        stop_file = '{0}/metrosim_files/stop_files/run_{1}.stop'.format(
            settings.BASE_DIR, run.id)
        open(stop_file, 'a').close()
        # Change the status of the run.
        run.status = 'Aborted'
        run.save()
    return HttpResponseRedirect(reverse(
        'metro:simulation_run_view', args=(simulation.id, run.id,)
    ))


@public_required
@check_run_relation
def simulation_run_view(request, simulation, run):
    """View with the current status, the results and the log of a run."""
    # Open and read the log file (if it exists).
    log_file = '{0}/metrosim_files/logs/run_{1}.txt'.format(settings.BASE_DIR,
                                                            run.id)
    log = None
    if os.path.isfile(log_file):
        with open(log_file, 'r') as f:
            log = f.read().replace('\n', '<br>')
    # Get the results of the run (if any).
    results = models.SimulationMOEs.objects.filter(runid=run.id)
    results = results.order_by('-day')
    result_table = tables.SimulationMOEsTable(results)
    context = {
        'simulation': simulation,
        'run': run,
        'log': log,
        'results': results,
        'result_table': result_table,
    }
    return render(request, 'metro_app/simulation_run.html', context)


@public_required
def simulation_run_list(request, simulation):
    """View with a list of the runs of the simulation."""
    runs = functions.get_query('run', simulation).order_by('-id')
    context = {
        'simulation': simulation,
        'runs': runs,
    }
    return render(request, 'metro_app/simulation_run_list.html', context)


@public_required
@check_run_relation
def simulation_run_link_output(request, simulation, run):
    """Simple view to send the link-specific results of the run to the user."""
    try:
        file_path = (
            '{0}/website_files/network_output/link_results_{1}_{2}.txt'
        ).format(settings.BASE_DIR, simulation.id, run.id)
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read())
            response['content_type'] = 'text/tab-separated-values'
            response['Content-Disposition'] = \
                'attachement; filename=link_results.tsv'
            return response
    except FileNotFoundError:
        # Should notify an admin that the file is missing.
        raise Http404()


@public_required
@check_run_relation
def simulation_run_user_output(request, simulation, run):
    """Simple view to send the user-specific results of the run to the user."""
    try:
        file_path = (
            '{0}/website_files/network_output/user_results_{1}_{2}.txt'
        ).format(settings.BASE_DIR, simulation.id, run.id)
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read())
            response['content_type'] = 'text/tab-separated-values'
            response['Content-Disposition'] = \
                'attachement; filename=user_results.tsv'
            return response
    except FileNotFoundError:
        # Should notify an admin that the file is missing.
        raise Http404()


@public_required
@check_run_relation
def simulation_run_user_path(request, simulation, run):
    """Simple view to send the user-specific results of the run to the user."""
    try:
        file_path = (
            '{0}/website_files/network_output/user_paths_{1}_{2}.tsv.gz'
        ).format(settings.BASE_DIR, simulation.id, run.id)
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read())
            response['content_type'] = 'text/tab-separated-values'
            response['content_encoding'] = 'gzip'
            response['Content-Disposition'] = \
                'attachement; filename=user_paths.tsv.gz'
            return response
    except FileNotFoundError:
        # Should notify an admin that the file is missing.
        raise Http404()


@public_required
def network_view(request, simulation):
    """View of the network of a simulation."""
    # If the network is large, the display method is different.
    links = functions.get_query('link', simulation)
    if links:
        large_network = links.count() > NETWORK_THRESHOLD
        # File where the data for the network are stored.
        output_file = (
            '{0}/website_files/network_output/network_{1!s}.json'
        ).format(settings.BASE_DIR, simulation.id)
        if simulation.has_changed or not os.path.isfile(output_file):
            # Generate a new output file.
            output = plots.network_output(simulation, large_network)
            with open(output_file, 'w') as f:
                json.dump(output, f)
            # Do not generate a new output file the next time (unless the
            # simulation changes).
            simulation.has_changed = False
            simulation.save()
        else:
            # Use data from the existing output file.
            with open(output_file, 'r') as f:
                output = json.load(f)
        context = {
            'simulation': simulation,
            'output': output,
            'large_network': large_network,
        }
        return render(request, 'metro_app/network.html', context)
    else:
        raise Http404()


@public_required
@check_run_relation
def network_view_run(request, simulation, run):
    """View of the network of a simulation with the disaggregated results of a
    specific run.
    """
    # If the network is large, the display method is different.
    links = functions.get_query('link', simulation)
    large_network = links.count() > NETWORK_THRESHOLD
    # Files where the data for the network are stored.
    network_file = (
        '{0}/website_files/network_output/network_{1}_{2}.json'
    ).format(settings.BASE_DIR, simulation.id, run.id)
    parameters_file = (
        '{0}/website_files/network_output/parameters_{1}_{2}.json'
    ).format(settings.BASE_DIR, simulation.id, run.id)
    results_file = (
        '{0}/website_files/network_output/results_{1}_{2}.json'
    ).format(settings.BASE_DIR, simulation.id, run.id)
    if (os.path.isfile(network_file)
            and os.path.isfile(parameters_file)
            and os.path.isfile(results_file)):
        # Load the data for the network.
        with open(network_file, 'r') as f:
            output = json.load(f)
        with open(parameters_file, 'r') as f:
            parameters = json.load(f)
        with open(results_file, 'r') as f:
            results = json.load(f)
        context = {
            'simulation': simulation,
            'output': output,
            'large_network': large_network,
            'parameters': parameters,
            'results': results,
        }
        return render(request, 'metro_app/network.html', context)
    else:
        # The network file for the run does not exist.
        return HttpResponseRedirect(reverse('metro:simulation_manager'))


# ====================
# Class-Based Views
# ====================

class MatrixListView(SingleTableMixin, FilterView):
    """Class-based view to show an OD Matrix as a table.
    The class must be initiated with one positional argument, the request, and
    two keyword arguments, simulation and demandsegment.
    """
    table_class = tables.MatrixTable
    model = models.Matrix
    template_name = 'metro_app/matrix_list.html'
    filterset_class = filters.MatrixFilter
    paginate_by = 25
    # With django-filters 2.0, strict = False is required to show the queryset
    # when no filter is active.
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        self.demandsegment = self.kwargs['demandsegment']
        queryset = models.Matrix.objects.filter(
            matrices=self.demandsegment.matrix)
        return queryset

    def get_context_data(self, **kwargs):
        context = super(MatrixListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['demandsegment'] = self.demandsegment
        context['total'] = self.demandsegment.matrix.total
        return context


class PTMatrixListView(SingleTableMixin, FilterView):
    """Class-based view to show the public-transit OD matrix as a table.
    This class is almost identical to MatrixListView.
    Two differences: table and filter used rename Population to Travel time;
    public_transit is True (allow changes in the template).
    """
    table_class = tables.PTMatrixTable
    model = models.Matrix
    template_name = 'metro_app/matrix_list.html'
    filterset_class = filters.PTMatrixFilter
    paginate_by = 25
    # With django-filters 2.0, strict = False is required to show the queryset
    # when no filter is active.
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = functions.get_query('public_transit', self.simulation)
        return queryset

    def get_context_data(self, **kwargs):
        context = super(PTMatrixListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['public_transit'] = True
        return context


class CentroidListView(SingleTableMixin, FilterView):
    table_class = tables.CentroidTable
    model = models.Centroid
    template_name = 'metro_app/object_list.html'
    filterset_class = filters.CentroidFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = functions.get_query(
            'centroid', self.simulation).order_by('user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(CentroidListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['object'] = 'centroid'
        return context


class CrossingListView(SingleTableMixin, FilterView):
    table_class = tables.CrossingTable
    model = models.Crossing
    template_name = 'metro_app/object_list.html'
    filterset_class = filters.CrossingFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = functions.get_query(
            'crossing', self.simulation).order_by('user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(CrossingListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['object'] = 'crossing'
        return context


class LinkListView(SingleTableMixin, FilterView):
    table_class = tables.LinkTable
    model = models.Link
    template_name = 'metro_app/object_list.html'
    filterset_class = filters.LinkFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = functions.get_query(
            'link', self.simulation).order_by('user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(LinkListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['object'] = 'link'
        return context


class FunctionListView(SingleTableMixin, FilterView):
    table_class = tables.FunctionTable
    model = models.Function
    template_name = 'metro_app/object_list.html'
    filterset_class = filters.FunctionFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = functions.get_query(
            'function', self.simulation).order_by('user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(FunctionListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['object'] = 'function'
        return context


class TollListView(SingleTableMixin, FilterView):
    table_class = tables.TollTable
    model = models.Policy
    template_name = 'metro_app/pricing_list.html'
    filterset_class = filters.TollFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = functions.get_query('policy', self.simulation)
        queryset = queryset.filter(type='PRICING')
        queryset = queryset.order_by('location__link__user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(TollListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        return context


# Shows all events
def show_events(request):
    """Sorts events by date"""
    event_list = models.Event.objects.order_by('-date')

    event_form = forms.EventForm()

    context = {'events': event_list, 'form': event_form}
    return render(request, 'metro_app/events_view.html', context)


@user_passes_test(lambda u: u.is_superuser)
def create_event(request):
    # Could be changed to a wrapper but can't figure out how to access user
    # from wrapper.
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse('metro:simulation_manager'))

    my_form = forms.EventForm(request.POST or None)
    if my_form.is_valid():
        event_title = my_form.cleaned_data['title']
        event_description = my_form.cleaned_data['description']
        event_author = request.user
        models.Event.objects.create(
            title=event_title, author=event_author,
            description=event_description,
        )

        my_form = forms.EventForm()

    return HttpResponseRedirect(reverse('metro:events_view'))


@user_passes_test(lambda u: u.is_superuser)
def delete_event(request, pk):
    # Could be changed to a wrapper but can't figure out how to access user
    # from wrapper.
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse('metro:simulation_manager'))

    event = get_object_or_404(models.Event, id=pk)

    if request.method == 'POST':
        event.delete()

    return HttpResponseRedirect(reverse('metro:events_view'))


# Loads the edit Event page
@user_passes_test(lambda u: u.is_superuser)
def edit_event_show(request, pk):
    # Could be changed to a wrapper but can't figure out how to access user
    # from wrapper.
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse('metro:simulation_manager'))

    event = get_object_or_404(models.Event, id=pk)
    my_form = forms.EventForm(
        initial={'title': event.title, 'description': event.description})

    context = {'event': event, 'form': my_form}
    return render(request, 'metro_app/events_edit.html', context)


@user_passes_test(lambda u: u.is_superuser)
def edit_event(request, pk):
    # Could be changed to a wrapper but can't figure out how to access user
    # from wrapper.
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse('metro:simulation_manager'))

    event = get_object_or_404(models.Event, id=pk)
    my_form = forms.EventForm(request.POST)

    if request.POST and my_form.is_valid():
        event_title = my_form.cleaned_data['title']
        event_description = my_form.cleaned_data['description']
        event_author = event.author
        event = models.Event.objects.filter(id=pk)
        event.update(
            title=event_title, author=event_author,
            description=event_description, date=datetime.datetime.now()
        )

    return HttpResponseRedirect(reverse('metro:events_view'))


def show_articles(request):
    article_list = models.Article.objects.order_by('-id')
    article_form = forms.ArticleForm()

    articles = []

    for article in article_list:
        documents = models.ArticleFile.objects.filter(file_article=article.id)
        articles.append(tuple((article, documents)))

    context = {'articles': articles, 'form': article_form}
    return render(request, 'metro_app/articles_view.html', context)


@login_required
def download_article_file(request, path):
    try:
        articles_path = (settings.BASE_DIR
                         + '/website_files/articles/')  # Change for linux
        file_path = articles_path + path
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                response = HttpResponse(f, content_type='application/pdf')
                response['Content-Disposition'] = \
                    'attachment; filename=' + os.path.basename(file_path)
                return response
        else:
            raise Http404()
    except FileNotFoundError:
        # Should notify an admin that the file is missing.
        raise Http404()


@user_passes_test(lambda u: u.is_superuser)
def create_article(request):
    # Could be changed to a wrapper but can't figure out how to access user
    # from wrapper.
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse('metro:simulation_manager'))

    my_form = forms.ArticleForm(request.POST or None)
    files = request.FILES.getlist('files')
    if my_form.is_valid():

        article_title = my_form.cleaned_data['title']
        article_description = my_form.cleaned_data['description']
        article_author = request.user

        article = models.Article(
            title=article_title, description=article_description,
            creator=article_author,
        )
        article.save()

        for f in files:
            file_name = os.path.basename(f.name)
            models.ArticleFile.objects.create(
                file=f, file_name=file_name, file_article=article)

        my_form = forms.ArticleForm()
    else:
        print(my_form.errors)

    return HttpResponseRedirect(reverse('metro:articles_view'))


@user_passes_test(lambda u: u.is_superuser)
def delete_article(request, pk):
    # Could be changed to a wrapper but can't figure out how to access user
    # from wrapper.
    if not request.user.is_superuser:
        return HttpResponseRedirect(reverse('metro:simulation_manager'))

    article = get_object_or_404(models.Article, id=pk)

    if request.method == 'POST':
        article.delete()

    return HttpResponseRedirect(reverse('metro:articles_view'))


@public_required
def simulation_export(request, simulation):
    """View to make a zip file of all simulation parameters."""

    dir_name = functions.get_export_directory()

    files_names = []

    files_names.append(
        functions.object_export_function(simulation, 'centroid', dir_name))
    files_names.append(
        functions.object_export_function(simulation, 'crossing', dir_name))
    files_names.append(
        functions.object_export_function(simulation, 'link', dir_name))
    files_names.append(
        functions.object_export_function(simulation, 'function', dir_name))
    files_names.append(
        functions.public_transit_export_function(simulation, dir_name))
    files_names.append(
        functions.pricing_export_function(simulation, dir_name))
    files_names.append(
        functions.usertype_export_function(simulation, dir_name=dir_name))

    demandsegments = functions.get_query('demandsegment', simulation)
    for demandsegment in demandsegments:
        files_names.append(
            functions.matrix_export_function(
                simulation, demandsegment, dir_name)
        )

    zipname = str(simulation).replace(' ', '_')

    s = BytesIO()

    file = zipfile.ZipFile(s, 'w')

    for f in files_names:
        if f is None:
            continue
        # Calculate path for file in zip
        fdir, fname = os.path.split(f)
        zip_path = os.path.join(zipname, fname)

        # Add file, at correct path
        file.write(f, zip_path)

    file.close()

    # Grab ZIP file from in-memory, make response with correct MIME-type
    response = HttpResponse(s.getvalue())
    response['content_type'] = 'application/x-zip-compressed'
    # ..and correct content-disposition
    response['Content-Disposition'] = \
        'attachment; filename={0}.zip'.format(zipname)

    # We delete the export directory to save disk space.
    shutil.rmtree(dir_name, ignore_errors=True)

    return response


@public_required
def traveler_simulation_export(request, simulation):
    """View to export usertypes and matrices in a zipfile."""

    dir_name = functions.get_export_directory()

    files_names = []

    files_names.append(
        functions.usertype_export_function(simulation, dir_name=dir_name))

    demandsegments = functions.get_query('demandsegment', simulation)
    for demandsegment in demandsegments:
        files_names.append(
            functions.matrix_export_function(
                simulation, demandsegment, dir_name)
        )

    zipname = str(simulation).replace(' ', '_')

    s = BytesIO()

    file = zipfile.ZipFile(s, 'w')

    for f in files_names:
        if f is None:
            continue
        # Calculate path for file in zip
        fdir, fname = os.path.split(f)
        zip_path = os.path.join(zipname, fname)

        # Add file, at correct path
        file.write(f, zip_path)

    file.close()

    # Grab ZIP file from in-memory, make response with correct MIME-type
    response = HttpResponse(s.getvalue())
    response['content_type'] = 'application/x-zip-compressed'
    # ..and correct content-disposition
    response['Content-Disposition'] = \
        'attachment; filename={0}.zip'.format(zipname)

    # We delete the export directory to save disk space.
    shutil.rmtree(dir_name, ignore_errors=True)

    return response


@require_POST
@login_required
def simulation_import_action(request):
    """This view is used when a user imports a new simulation.
    The request should contain data for the new simulation (name, comment and
    public) and a zipfile with the simulation data.
    """
    # Create a form with the data sent and check if it is valid.
    form = forms.SimulationImportForm(
        request.user, request.POST, request.FILES)
    if form.is_valid():
        # Create a new simulation with the attributes sent.
        simulation = functions.create_simulation(request.user, form)
        # Import the zipfile data in the simulation.
        encoded_file = form.cleaned_data['zipfile']
        file = zipfile.ZipFile(encoded_file)
        namelist = file.namelist()
        for filename in namelist:
            if re.search('/zones.[tc]sv$', filename):
                functions.object_import_function(
                    file.open(filename), simulation, 'centroid')
                break

        for filename in namelist:
            if re.search('/intersections.[tc]sv$', filename):
                functions.object_import_function(
                    file.open(filename), simulation, 'crossing')
                break

        for filename in namelist:
            if re.search('/links.[tc]sv$', filename):
                functions.object_import_function(
                    file.open(filename), simulation, 'link')
                break

        for filename in namelist:
            if re.search('/congestion_functions.[tc]sv$', filename):
                functions.object_import_function(
                    file.open(filename), simulation, 'function')
                break

        for filename in namelist:
            if re.search('/public_transit.[tc]sv$', filename):
                functions.public_transit_import_function(
                    file.open(filename), simulation)
                break

        for filename in namelist:
            if re.search('/traveler_types.[tc]sv$', filename):
                functions.usertype_import_function(
                    file.open(filename), simulation)
                break

        demandsegments = functions.get_query('demandsegment', simulation)
        for filename in namelist:
            d = re.search('/matrix_([0-9]+).[tc]sv$', filename)
            if d:
                # Get the demandsegment associated with this OD matrix.
                user_id = d.group(1)
                try:
                    demandsegment = demandsegments.get(
                        usertype__user_id=user_id)
                except models.DemandSegment.objects.DoesNotExist:
                    # Matrix file with an invalid id, ignore it.
                    continue
                # Import the matrix file in the new demandsegment.
                functions.matrix_import_function(
                    file.open(filename), simulation, demandsegment)

        for filename in namelist:
            if re.search('/pricings.[tc]sv$', filename):
                functions.pricing_import_function(
                    file.open(filename), simulation)
                break

        return HttpResponseRedirect(
            reverse('metro:simulation_view', args=(simulation.id,))
        )
    else:
        return HttpResponseRedirect(
            reverse('metro:simulation_manager')
        )


@require_POST
@owner_required
def traveler_import_action(request, simulation):
    """View to import usertypes and matrices from a zipfile."""
    # Create a form with the data send and check if it is valid.
    try:
        form = forms.ImportForm(request.POST, request.FILES)
        if form.is_valid():
            encoded_file = form.cleaned_data['import_file']
            file = zipfile.ZipFile(encoded_file)
            namelist = file.namelist()

            for filename in namelist:
                if re.search('/traveler_types.[tc]sv$', filename):
                    functions.usertype_import_function(
                        file.open(filename), simulation)
                    break

            demandsegments = functions.get_query('demandsegment', simulation)
            for filename in namelist:
                d = re.search('/matrix_([0-9]+).[tc]sv$', filename)
                if d:
                    # Get the demandsegment associated with this OD matrix.
                    user_id = d.group(1)
                    try:
                        demandsegment = demandsegments.get(
                            usertype__user_id=user_id)
                    except models.DemandSegment.DoesNotExist:
                        # Matrix file with an invalid id, ignore it.
                        continue
                    # Import the matrix file in the new demandsegment.
                    functions.matrix_import_function(
                        file.open(filename), simulation, demandsegment)

    except Exception as e:
        # Catch any exception while importing the file and return an error page
        # if there is any.
        print(e)
        context = {
            'simulation': simulation,
            'object': 'zipfile',
        }
        return render(request, "metro_app/import_error.html", context)

    else:

        return HttpResponseRedirect(reverse(
            'metro:demand_view', args=(simulation.id,)
        ))


@require_POST
@owner_required
def usertype_import(request, simulation):
    """View to convert the imported file to usertype in the database."""
    try:
        encoded_file = request.FILES['import_file']
        functions.usertype_import_function(encoded_file, simulation)
    except Exception as e:
        # Catch any exception while importing the file and return an error page
        # if there is any.
        print(e)
        context = {
            'simulation': simulation,
            'object': 'usertype',
        }
        return render(request, 'metro_app/import_error.html', context)
    else:
        return HttpResponseRedirect(reverse(
            'metro:demand_view', args=(simulation.id,)
        ))


@public_required
@check_demand_relation
def usertype_export(request, simulation, demandsegment):
    """View to send a file with the usertype parameters."""
    dir_name = functions.get_export_directory()
    filename = functions.usertype_export_function(
        simulation, demandsegment, dir_name)
    if filename is None:
        return Http404()
    with codecs.open(filename, 'r', encoding='utf8') as f:
        # Build a response to send a file.'beta_mean',
        response = HttpResponse(f.read())
        response['content_type'] = 'text/tab-separated-values'
        name = '{}.tsv'.format(demandsegment.usertype).replace(' ', '_')
        response['Content-Disposition'] = \
            'attachement; filename={}'.format(name)
    # We delete the export directory to save disk space.
    shutil.rmtree(dir_name, ignore_errors=True)
    return response


@login_required
def environments_view(request):
    if request.user.is_authenticated:
        auth_environments = models.Environment.objects.filter(
            users=request.user)
    else:
        auth_environments = {}
    form = forms.EnvironmentForm()

    permission = request.user.has_perm('metro_app.add_environment')

    context = {
        'environments': auth_environments,
        'form': form,
        'permission': permission,
    }
    return render(request, 'metro_app/environments_view.html', context)


@login_required
@environment_can_create
def environment_create(request):
    my_form = forms.EnvironmentForm(request.POST or None)
    if my_form.is_valid():
        env_name = my_form.cleaned_data['name']
        env_user = {request.user}

        environment = models.Environment.objects.create(
            name=env_name, creator=env_user)
        environment.users.set(env_user)

        my_form = forms.EnvironmentForm()
    return HttpResponseRedirect(reverse('metro:environments_view'))


@login_required
@environment_owner_required
def environment_add_view(request, environment):
    env = get_object_or_404(models.Environment, id=environment)
    my_form = forms.EnvironmentUserAddForm()

    context = {'environment': env, 'form': my_form, 'error': False}

    return render(request, 'metro_app/environments_edit.html', context)


@login_required
@environment_owner_required
def environment_add(request, environment):
    env = get_object_or_404(models.Environment, id=environment)
    my_form = forms.EnvironmentUserAddForm(request.POST or None)
    if my_form.is_valid():
        username = my_form.cleaned_data['username']
        user = User.objects.get(username=username)

        env.users.add(user)

        my_form = forms.EnvironmentUserAddForm()
        return HttpResponseRedirect(reverse('metro:environments_view'))

    context = {
        'environment': env,
        'form': my_form,
        'error': True,
    }
    return render(request, 'metro_app/environments_edit.html', context)


@login_required
@environment_owner_required
def environment_user_delete(request, environment, user):
    env = get_object_or_404(models.Environment, id=environment)

    if request.method == 'POST':
        env.users.remove(user)

    return HttpResponseRedirect(reverse('metro:environments_view'))


@login_required
@environment_owner_required
def environment_delete(request, environment):
    env = get_object_or_404(models.Environment, id=environment)
    env.delete()

    return HttpResponseRedirect(reverse('metro:environments_view'))


@require_POST
@owner_required
def batch_new(request, simulation):
    """View to create a new batch run."""
    batch_form = forms.BatchForm(request.POST)
    if batch_form.is_valid():
        # Save the batch and its runs.
        batch = batch_form.save(simulation)
        for i in range(batch.nb_runs):
            run = models.BatchRun()
            run.batch = batch
            run.run_order = i+1
            run.save()
        # Return the view to edit the batch.
        return HttpResponseRedirect(
            reverse('metro:batch_edit', args=(simulation.id, batch.id,))
        )
    else:
        return HttpResponseRedirect(reverse('metro:simulation_manager'))


@owner_required
@check_batch_relation
def batch_edit(request, simulation, batch):
    """View to edit the files of a batch run."""
    # Create a formset to edit the files.
    BatchRunFormSet = forms.modelformset_factory(
        models.BatchRun,
        form=forms.BatchRunForm,
        extra=0,
    )
    batch_runs = models.BatchRun.objects.filter(batch=batch)
    batch_form_set = BatchRunFormSet(queryset=batch_runs)
    context = {
        'simulation': simulation,
        'batch': batch,
        'formset': batch_form_set,
    }
    return render(request, 'metro_app/batch_edit.html', context)


@require_POST
@owner_required
@check_batch_relation
def batch_save(request, simulation, batch):
    """View to save the formset of a batch."""
    BatchRunFormSet = forms.modelformset_factory(
        models.BatchRun,
        form=forms.BatchRunForm,
        extra=0,
    )
    formset = BatchRunFormSet(request.POST, request.FILES)
    if formset.is_valid():
        formset.save()
        return HttpResponseRedirect(
            reverse('metro:batch_view', args=(simulation.id, batch.id,))
        )
    else:
        context = {
            'simulation': simulation,
            'form': formset,
        }
        return render(request, 'metro_app/errors.html', context)


@public_required
@check_batch_relation
def batch_view(request, simulation, batch):
    """View to show data on a batch (runs, status)."""
    is_owner = functions.can_edit(request.user, simulation)
    # Here we should run the batch, if is_owner is True and if the batch is not
    # running already.
    runs = models.BatchRun.objects.filter(batch=batch)
    context = {
        'simulation': simulation,
        'batch': batch,
        'runs': runs,
        'is_owner': is_owner,
    }
    return render(request, 'metro_app/batch_view.html', context)


@public_required
def batch_history(request, simulation):
    batchs = functions.get_query('batch', simulation)
    context = {
        'simulation': simulation,
        'batchs': batchs,
    }
    return render(request, 'metro_app/batch_history.html', context)


# ====================
# Receivers
# ====================

@receiver(pre_delete, sender=models.FunctionSet)
def pre_delete_function_set(sender, instance, **kwargs):
    """Delete all objects related to a functionset before deleting the
    functionset.
    """
    # Delete all functions (this also deletes the links).
    instance.function_set.all().delete()


@receiver(pre_delete, sender=models.Demand)
def pre_delete_demand(sender, instance, **kwargs):
    """Delete all demand segments before deleting the demand."""
    demandsegments = instance.demandsegment_set.all()
    for demandsegment in demandsegments:
        usertype = demandsegment.usertype
        matrix = demandsegment.matrix
        alphaTI = usertype.alphaTI
        alphaTP = usertype.alphaTP
        beta = usertype.beta
        delta = usertype.delta
        departureMu = usertype.departureMu
        gamma = usertype.gamma
        routeMu = usertype.routeMu
        modeMu = usertype.modeMu
        tstar = usertype.tstar
        penaltyTP = usertype.penaltyTP
        alphaTI.delete()
        alphaTP.delete()
        beta.delete()
        delta.delete()
        gamma.delete()
        departureMu.delete()
        routeMu.delete()
        modeMu.delete()
        penaltyTP.delete()
        tstar.delete()
        # Delete the matrix (the demand segment should be already deleted).
        matrix.delete()


# ====================
#  Functions
# ====================

def gen_formset(object_name, simulation, request=None):
    """Function to generate a formset either from a simulation object or from a
    request object.
    If there is no existing instance of the object, create a formset with an
    empty form (it is impossible to add the first form otherwise).
    """
    formset = None
    query = functions.get_query(object_name, simulation)
    if object_name == 'centroid':
        if request:
            if query.exists():
                formset = forms.CentroidFormSet(
                    request.POST,
                    prefix='centroid',
                    simulation=simulation,
                )
            else:
                formset = forms.CentroidFormSetExtra(
                    request.POST,
                    prefix='centroid',
                    simulation=simulation,
                )
        else:
            if query.exists():
                formset = forms.CentroidFormSet(
                    queryset=query,
                    prefix='centroid',
                    simulation=simulation,
                )
            else:
                formset = forms.CentroidFormSetExtra(
                    queryset=query,
                    prefix='centroid',
                    simulation=simulation,
                )
    elif object_name == 'crossing':
        if request:
            if query.exists():
                formset = forms.CrossingFormSet(
                    request.POST,
                    prefix='crossing',
                    simulation=simulation,
                )
            else:
                formset = forms.CrossingFormSetExtra(
                    request.POST,
                    prefix='crossing',
                    simulation=simulation,
                )
        else:
            if query.exists():
                formset = forms.CrossingFormSet(
                    queryset=query,
                    prefix='crossing',
                    simulation=simulation,
                )
            else:
                formset = forms.CrossingFormSetExtra(
                    queryset=query,
                    prefix='crossing',
                    simulation=simulation,
                )
    elif object_name == 'link':
        if request:
            if query.exists():
                formset = forms.LinkFormSet(
                    request.POST,
                    prefix='link',
                    simulation=simulation,
                    form_kwargs={'simulation': simulation},
                )
            else:
                formset = forms.LinkFormSetExtra(
                    request.POST,
                    prefix='link',
                    simulation=simulation,
                    form_kwargs={'simulation': simulation},
                )
        else:
            if query.exists():
                formset = forms.LinkFormSet(
                    queryset=query,
                    prefix='link',
                    simulation=simulation,
                    form_kwargs={'simulation': simulation}
                )
            else:
                formset = forms.LinkFormSetExtra(
                    queryset=query,
                    prefix='link',
                    simulation=simulation,
                    form_kwargs={'simulation': simulation}
                )
    elif object_name == 'function':
        if request:
            if query.exists():
                formset = forms.FunctionFormSet(
                    request.POST,
                    prefix='function',
                    simulation=simulation,
                )
            else:
                formset = forms.FunctionFormSetExtra(
                    request.POST,
                    prefix='function',
                    simulation=simulation,
                )
        else:
            if query.exists():
                formset = forms.FunctionFormSet(
                    queryset=query,
                    prefix='function',
                    simulation=simulation,
                )
            else:
                formset = forms.FunctionFormSetExtra(
                    queryset=query,
                    prefix='function',
                    simulation=simulation,
                )
    return formset
