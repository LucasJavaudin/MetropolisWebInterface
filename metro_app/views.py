"""This file defines the views of the website.

Author: Lucas Javaudin
E-mail: lucas.javaudin@ens-paris-saclay.fr
"""
import time
import urllib
import re
import os
import csv
import subprocess
from io import StringIO
from shutil import copyfile
import json
import codecs
from math import sqrt
import numpy as np
import pandas as pd

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, FileResponse
from django.http import Http404
from django.urls import reverse
from django.views.generic import TemplateView
from django.views.decorators.http import require_POST
from django.conf import settings
from django.contrib.auth import authenticate, logout, login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from django.utils import timezone
from django.db import connection

from django_filters.views import FilterView
from django_tables2.views import SingleTableMixin

import metro_app

from metro_app.models import *
from metro_app.forms import *
from metro_app.plots import *
from metro_app.tables import *
from metro_app.filters import *
from metro_app.functions import *

import logging

# Get an instance of a logger.
logger = logging.getLogger(__name__)

# Thresholds for the number of centroids required for a simulation to be
# considered as having a large OD Matrix.
MATRIX_THRESHOLD = 10
# Thresholds for the number of links required for a simulation to be
# considered as having a large network.
NETWORK_THRESHOLD = 1000
# Maximum number of instances that can be edited at the same time in the
# object_edit view.
OBJECT_THRESHOLD = 80


#====================
# Decorators
#====================

def public_required(view):
    """Decorator to execute a function only if the requesting user has view
    access to the simulation.

    The decorator also converts the simulation id parameter to a Simulation
    object.
    """
    def wrap(*args, **kwargs):
        user = args[0].user # The first arg is the request object.
        simulation_id = kwargs.pop('simulation_id')
        simulation = get_object_or_404(Simulation, pk=simulation_id)
        if can_view(user, simulation):
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
        user = args[0].user # The first arg is the request object.
        simulation_id = kwargs.pop('simulation_id')
        simulation = get_object_or_404(Simulation, pk=simulation_id)
        if can_edit(user, simulation):
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
        demandsegment = get_object_or_404(DemandSegment, pk=demandsegment_id)
        if simulation.scenario.demand == demandsegment.demand.first():
            return view(*args, simulation=simulation,
                        demandsegment=demandsegment)
        else:
            # The demand segment id not related to the simulation.
            return HttpResponseRedirect(reverse('metro:simulation_manager'))
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
        run = get_object_or_404(SimulationRun, pk=run_id)
        if run.simulation == simulation:
            return view(*args, simulation=simulation,
                        run=run)
        else:
            # The run id not related to the simulation.
            return HttpResponseRedirect(reverse('metro:simulation_manager'))
    return wrap


#====================
# Views
#====================

def simulation_manager(request):
    """Home page of Metropolis.

    This view shows lists of simulations and proposes a form to create a new
    simulation.
    """
    # Create lists of simulations.
    simulation_user_list = Simulation.objects.filter(user_id=request.user.id)
    simulation_public_list = \
        Simulation.objects.filter(public=True).exclude(user_id=request.user.id)
    simulation_private_list = None
    if request.user.is_superuser:
        # Superuser can see private simulations.
        simulation_private_list = \
            Simulation.objects.filter(public=False).exclude(user=request.user)
    # Create a form for new simulations.
    simulation_form = BaseSimulationForm()
    # Create a form for copied simulations (the form has the same fields as the
    # form for new simulations, we add the prefix copy to differentiate the
    # two).
    copy_form = BaseSimulationForm(prefix='copy')
    context = {
        'simulation_user_list': simulation_user_list,
        'simulation_public_list': simulation_public_list,
        'simulation_private_list': simulation_private_list,
        'simulation_form': simulation_form,
        'copy_form': copy_form,
    }
    return render(request, 'metro_app/simulation_manager.html', context)

def register(request):
    """View to show the register form."""
    register_form = UserCreationForm()
    return render(request, 'metro_app/register.html', {'form': register_form})

def login_view(request, login_error=False):
    """View to show the login form."""
    login_form = LoginForm()
    context = {
        'form': login_form,
        'login_error': login_error,
    }
    return render(request, 'metro_app/login.html', context)

def register_action(request):
    """View triggered when an user submit a register form."""
    if request.method == 'POST':
        register_form = UserCreationForm(request.POST)
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
        login_form = LoginForm(request.POST)
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
            # If a problem occured, return to the login page and show the errors.
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

def how_to(request):
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
    form = BaseSimulationForm(request.POST)
    if form.is_valid():
        # Create a new simulation with the attributes sent.
        simulation = Simulation()
        simulation.user = request.user
        simulation.name = form.cleaned_data['name']
        simulation.comment = form.cleaned_data['comment']
        simulation.public = form.cleaned_data['public']
        # Create models associated with the new simulation.
        network = Network()
        network.name = simulation.name
        network.save()
        function_set = FunctionSet()
        function_set.name = simulation.name
        function_set.save()
        # Add defaults functions.
        function = Function(name='Free flow', user_id=1,
                            expression='3600*(length/speed)')
        function.save()
        function.vdf_id = function.id
        function.save()
        function.functionset.add(function_set)
        function = Function(name='Bottleneck function', user_id=2,
                            expression=('3600*((dynVol<=(lanes*capacity*length'
                                        + '/speed))*(length/speed)+(dynVol>'
                                        + '(lanes*capacity*length/speed))*'
                                        + '(dynVol/(capacity*lanes)))'))
        function.save()
        function.vdf_id = function.id
        function.save()
        function.functionset.add(function_set)
        # Log density is not working somehow.
        # function = Function(name='Log density', user_id=3,
                            # expression=('3600*(length/speed)'
                                        # '*((dynVol<=8.0*lanes*length)'
                                        # '+(dynVol>8.0*lanes*length)'
                                        # '*((dynVol<0.9*130.0*lanes*length)'
                                        # '*ln(130.0/8.0)'
                                        # '/ln(130.0*lanes*length/(dynVol+0.01))'
                                        # '+(dynVol>=0.9*130.0*lanes*length)'
                                        # '*ln(130.0/8.0)/ln(1/0.9)))'))
        # function.save()
        # function.vdf_id = function.id
        # function.save()
        # function.functionset.add(function_set)
        pttimes = Matrices()
        pttimes.save()
        supply = Supply()
        supply.name = simulation.name
        supply.network = network
        supply.functionset = function_set
        supply.pttimes = pttimes
        supply.save()
        demand = Demand()
        demand.name = simulation.name
        demand.save()
        scenario = Scenario()
        scenario.name = simulation.name
        scenario.supply = supply
        scenario.demand = demand
        scenario.save()
        # Save the simulation and return its view.
        simulation.scenario = scenario
        simulation.save()
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
    """
    copy_form = BaseSimulationForm(request.POST, prefix='copy')
    if copy_form.is_valid():
        # The simulation id is hidden in an input of the pop-up (the id is
        # changed by javascript.
        simulation_id = request.POST['copy_id']
        simulation = get_object_or_404(Simulation, pk=simulation_id)
        # There are timeouts if the same simulation is copied twice
        # simultaneously so we wait until the simulation is unlocked.
        while simulation.locked:
            # Wait 5 seconds.
            time.sleep(5)
            simulation = get_object_or_404(Simulation, pk=simulation_id)
        # Lock the simulation.
        simulation.locked = True
        simulation.save()
        # Use a direct access to the database.
        with connection.cursor() as cursor:
            # Copy all the models associated with the new simulation.
            # (1) Supply.
            functionset = FunctionSet.objects.get(
                pk=simulation.scenario.supply.functionset.id
            )
            functionset.pk = None
            functionset.save()
            network = Network.objects.get(pk=simulation.scenario.supply.network.id)
            network.pk = None
            network.save()
            # (1.1) Links.
            # Find last link id right before executing the raw SQL query.
            last_id = Link.objects.last().id
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
            new_last_id = Link.objects.last().id
            # Add the many-to-many relations between links and network.
            cursor.execute(
                "INSERT INTO Network_Link (network_id, link_id) "
                "SELECT '%s', id FROM Link WHERE id > %s and id <= %s;",
                [network.id, last_id, new_last_id]
            )
            # (1.2) Functions.
            # Find last function id.
            last_id = Function.objects.last().id
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
            new_last_id = Function.objects.last().id
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
            last_id = Centroid.objects.last().id
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
            new_last_id = Centroid.objects.last().id
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
                "JOIN Network_Link "
                "ON Link.id = Network_Link.link_id "
                "SET Link.origin = centroid_ids.new "
                "WHERE Network_Link.network_id = %s;",
                [network.id]
            )
            cursor.execute(
                "UPDATE Link "
                "JOIN centroid_ids "
                "ON Link.destination = centroid_ids.old "
                "JOIN Network_Link "
                "ON Link.id = Network_Link.link_id "
                "SET Link.destination = centroid_ids.new "
                "WHERE Network_Link.network_id = %s;",
                [network.id]
            )
            # (1.4) Crossings.
            # Find last crossing id.
            last_id = Crossing.objects.last().id
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
            new_last_id = Crossing.objects.last().id
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
                "JOIN Network_Link "
                "ON Link.id = Network_Link.link_id "
                "SET Link.origin = crossing_ids.new "
                "WHERE Network_Link.network_id = %s;",
                [network.id]
            )
            cursor.execute(
                "UPDATE Link "
                "JOIN crossing_ids "
                "ON Link.destination = crossing_ids.old "
                "JOIN Network_Link "
                "ON Link.id = Network_Link.link_id "
                "SET Link.destination = crossing_ids.new "
                "WHERE Network_Link.network_id = %s;",
                [network.id]
            )
            # (1.5) Public transit.
            pttimes = Matrices.objects.get(pk=simulation.scenario.supply.pttimes.id)
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
            supply = Supply.objects.get(pk=simulation.scenario.supply.id)
            supply.pk = None
            supply.network = network
            supply.functionset = functionset
            supply.pttimes = pttimes
            supply.save()
            # (2) Demand.
            demand = Demand.objects.get(pk=simulation.scenario.demand.id)
            demand_segments = demand.demandsegment_set.all()
            demand.pk = None
            demand.save()
            for demand_segment in demand_segments:
                # (2.1) UserType.
                usertype = UserType.objects.get(pk=demand_segment.usertype.id)
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
                matrix = Matrices.objects.get(pk=demand_segment.matrix.id)
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
            scenario = Scenario.objects.get(pk=simulation.scenario.id)
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
            # Here, we could copy the json file of the copied simulation if the
            # copied simulation has not changed. For now, I only put has_changed
            # to True for the new simulation so that a new json file will be
            # generated.
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
    SimulationMOEs.objects.filter(simulation=simulation.id).delete()
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
    owner = can_edit(request.user, simulation)
    # Create the form to copy the simulation.
    copy_form = BaseSimulationForm(prefix='copy')
    # Create the form to edit name, comment and public.
    edit_form = BaseSimulationForm(instance=simulation)
    # Create the form to edit the parameters.
    simulation_form = ParametersSimulationForm(owner=owner,
                                               instance=simulation)
    # Count the number of each elements in the network.
    network = dict()
    network['centroids'] = get_query('centroid', simulation).count()
    network['crossings'] = get_query('crossing', simulation).count()
    network['links'] = get_query('link', simulation).count()
    network['functions'] = get_query('function', simulation).count()
    # File where the data for the network are stored.
    output_file = (
        '{0}/website_files/network_output/network_{1!s}.json'
        .format(settings.BASE_DIR, simulation.id)
    )
    network['generated'] = (os.path.isfile(output_file)
                            and not simulation.has_changed)
    # Count the number of user types.
    travelers = dict()
    travelers['type'] = get_query('usertype', simulation).count()
    # Count the number of travelers
    matrices = get_query('matrices', simulation)
    nb_travelers = matrices.aggregate(Sum('total'))['total__sum']
    if nb_travelers is None:
        nb_travelers = 0
    else:
        nb_travelers = int(nb_travelers)
    travelers['nb_travelers'] = nb_travelers
    # Count the number of runs.
    simulation_runs = get_query('run', simulation)
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
    complete_simulation = (network['centroids'] > 1 
                           and network['crossings'] > 0
                           and network['links'] > 0
                           and network['functions'] > 0
                           and travelers['nb_travelers'] > 0)
    # Check if there is a public transit network (in case modal choice is
    # enabled).
    good_pt = True
    if not get_query('public_transit', simulation).exists():
        usertypes = get_query('usertype', simulation)
        modal_choice = False
        for usertype in usertypes:
            if usertype.modeChoice == 'true':
                modal_choice = True
        if modal_choice:
            good_pt = False
    # Create a form to run the simulation.
    run_form = None
    if owner and complete_simulation:
        run_form = RunForm(initial={'name': 'Run {}'.format(runs['nb_run']+1)})
    context = {
        'simulation': simulation,
        'owner': owner,
        'copy_form': copy_form,
        'edit_form': edit_form,
        'simulation_form': simulation_form,
        'network': network,
        'travelers': travelers,
        'runs': runs,
        'complete_simulation': complete_simulation,
        'good_pt': good_pt,
        'run_form': run_form,
    }
    return render(request, 'metro_app/simulation_view.html', context)

@require_POST
@owner_required
def simulation_view_save(request, simulation):
    """View to save the changes to the simulation parameters."""
    simulation_form = ParametersSimulationForm(owner=True, data=request.POST,
                                               instance=simulation)
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
    edit_form = BaseSimulationForm(data=request.POST, instance=simulation)
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
            'form': simulation_form,
        }
        return render(request, 'metro_app/errors.html', context)

@public_required
def demand_view(request, simulation):
    """Main view to list and edit the user types."""
    demandsegments = get_query('demandsegment', simulation)
    owner = can_edit(request.user, simulation)
    # The matrix cannot be edit if the number of centroids is too large.
    nb_centroids = get_query('centroid', simulation).count()
    large_matrix = nb_centroids > MATRIX_THRESHOLD
    # The matrix is empty if there is no centroid.
    has_centroid = nb_centroids > 0
    # Create a form to import OD matrices.
    import_form = ImportForm()
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
    alphaTI = Distribution(type='NONE', mean=10)
    alphaTP = Distribution(type='NONE', mean=15)
    beta = Distribution(type='NONE', mean=5)
    delta = Distribution(type='NONE', mean=10)
    departureMu = Distribution(type='NONE', mean=2)
    gamma = Distribution(type='NONE', mean=20)
    modeMu = Distribution(type='NONE', mean=5)
    penaltyTP = Distribution(type='NONE', mean=2)
    routeMu = Distribution(type='NONE', mean=10)
    # Default value for t star is average arrival at middle of period and
    # uniform distribution over half of the period.
    mid_time = (simulation.startTime + simulation.lastRecord) / 2
    length = simulation.lastRecord - simulation.startTime
    tstar = Distribution(type='UNIFORM', mean=mid_time, std=length/(4*sqrt(3)))
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
    usertype = UserType()
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
    usertype.save()
    # Create a demand segment and a matrix for the user type.
    matrix = Matrices()
    matrix.save()
    demandsegment = DemandSegment()
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
    form = UserTypeForm(instance=demandsegment.usertype)
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
    form = UserTypeForm(data=request.POST, instance=demandsegment.usertype)
    if form.is_valid():
        form.save()
        # Check if value of scale has changed.
        demandsegment.refresh_from_db()
        if demandsegment.scale != scale:
            # Update total population.
            matrix = demandsegment.matrix
            matrix_points = Matrix.objects.filter(matrices=matrix)
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
    centroids = get_query('centroid', simulation)
    has_centroid = centroids.count() >= 2
    large_matrix = centroids.count() > MATRIX_THRESHOLD
    # Get an import form.
    import_form = ImportForm()
    # Check ownership.
    owner = can_edit(request.user, simulation)
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
    centroids = get_query('centroid', simulation)
    if centroids.count() > MATRIX_THRESHOLD:
        # Large matrix, return a table instead.
        return MatrixListView.as_view()(request, simulation=simulation,
                                        demandsegment=demandsegment)
    else:
        # Small matrix, return it.
        matrix = demandsegment.matrix
        matrix_points = Matrix.objects.filter(matrices=matrix)
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
                    except Matrix.DoesNotExist:
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
    matrix_points = Matrix.objects.filter(matrices=matrix)
    centroids = get_query('centroid', simulation)
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
    formset = MatrixFormSet(
        queryset=Matrix.objects.filter(matrices=matrix),
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
    formset = MatrixFormSet(request.POST)
    if formset.is_valid():
        formset.save()
        # Update total.
        matrix_points = Matrix.objects.filter(matrices=matrix)
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
    matrix = demandsegment.matrix
    matrix_couples = Matrix.objects.filter(matrices=matrix)
    # To avoid conflict if two users export a file at the same time, we
    # generate a random name for the export file.
    seed = np.random.randint(10000)
    filename = '{0}/website_files/exports/{1}.tsv'.format(settings.BASE_DIR,
                                                          seed)
    with codecs.open(filename, 'w', encoding='utf8') as f:
        writer = csv.writer(f, delimiter='\t')
        # Get a dictionary with all the values to export.
        values = matrix_couples.values_list('p__user_id', 'q__user_id', 'r')
        # Write a custom header.
        writer.writerow(['origin', 'destination', 'population'])
        writer.writerows(values)
    with codecs.open(filename, 'r', encoding='utf8') as f:
        # Build a response to send a file.
        response = HttpResponse(f.read())
        response['content_type'] = 'text/tab-separated-values'
        response['Content-Disposition'] = 'attachement; filename=od_matrix.tsv'
    # We delete the export file to save disk space.
    os.remove(filename)
    return response

@require_POST
@owner_required
@check_demand_relation
def matrix_import(request, simulation, demandsegment):
    """View to convert the imported file to an O-D matrix in the database.
    
    This view could be much more simple but I tried to use as little as
    possible Django ORM (the querysets). When written with standard Django
    querysets and save methods, it took hours to import a large OD matrix.
    Basicaly, this view looks at each row in the imported file to know if the
    OD pair of the row already exists or needs to be created. If it already
    exists, the view looks at the population value to know if the value needs
    to be updated. To update values, we simply delete the previous entries in
    the database and insert the new ones.
    """
    try:
        # Create a set with all existing OD pairs in the OD matrix.
        matrix = demandsegment.matrix
        pairs = Matrix.objects.filter(matrices=matrix)
        existing_pairs = set(pairs.values_list('p_id', 'q_id'))
        # Create a dictionary to map the centroid user ids with the centroid
        # objects.
        centroids = get_query('centroid', simulation)
        centroid_mapping = dict()
        centroid_id_mapping = dict()
        for centroid in centroids:
            centroid_mapping[centroid.user_id] = centroid
            centroid_id_mapping[centroid.user_id] = centroid.id
        # Convert the imported file to a csv DictReader.
        encoded_file = request.FILES['import_file']
        tsv_file = StringIO(encoded_file.read().decode())
        reader = csv.DictReader(tsv_file, delimiter='\t')
        # For each imported OD pair, if the pair already exists in the OD Matrix,
        # it is stored to be updated, else it is stored to be created.
        to_be_updated = set()
        to_be_created = list()
        for row in reader:
            pair = (
                centroid_id_mapping[int(row['origin'])],
                centroid_id_mapping[int(row['destination'])]
            )
            if pair in existing_pairs:
                to_be_updated.add((*pair, float(row['population'])))
            else:
                to_be_created.append(
                    Matrix(p=centroid_mapping[int(row['origin'])],
                           q=centroid_mapping[int(row['destination'])],
                           r=float(row['population']),
                           matrices=matrix)
                )
        if to_be_updated:
            # Create a mapping between the values (p, q, r) and the ids.
            pair_values = set(pairs.values_list('id', 'p_id', 'q_id'))
            pair_mapping = dict()
            for pair in pair_values:
                pair_mapping[pair[1:]] = pair[0]
            pair_values = set(pairs.values_list('id', 'p_id', 'q_id', 'r'))
            # Find the pairs that really need to be updated (i.e. r is also
            # different).
            pair_values = set(pairs.values_list('p_id', 'q_id', 'r'))
            to_be_updated = to_be_updated.difference(pair_values)
            # Retrieve the ids of the pairs to be updated with the mapping and
            # delete them.
            to_be_updated_ids = [pair_mapping[pair[:2]] for pair in to_be_updated]
            with connection.cursor() as cursor:
                chunk_size = 20000
                chunks = [to_be_updated_ids[x:x+chunk_size]
                          for x in range(0, len(to_be_updated_ids), chunk_size)]
                for chunk in chunks:
                    cursor.execute(
                        "DELETE FROM Matrix "
                        "WHERE id IN %s;",
                        [chunk]
                    )
            # Create a mapping between the centroids ids and the centroid objects.
            centroid_id_mapping = dict()
            for centroid in centroids:
                centroid_id_mapping[centroid.id] = centroid
            # Now, create the updated pairs with the new values.
            to_be_created += [
                Matrix(p=centroid_id_mapping[pair[0]],
                       q=centroid_id_mapping[pair[1]],
                       r=pair[2],
                       matrices=matrix)
                for pair in to_be_updated
            ]
        # Create the new OD pairs in bulk.
        # The chunk size is limited by the MySQL engine (timeout if it is too big).
        chunk_size = 20000
        chunks = [to_be_created[x:x+chunk_size] 
                  for x in range(0, len(to_be_created), chunk_size)]
        for chunk in chunks:
            Matrix.objects.bulk_create(chunk, chunk_size)
        # Update total.
        pairs = pairs.all() # Update queryset from database.
        matrix.total = int(
            demandsegment.scale * pairs.aggregate(Sum('r'))['r__sum']
        )
        matrix.save()
        simulation.has_changed = True
        simulation.save()
        return HttpResponseRedirect(reverse(
            'metro:matrix_view', args=(simulation.id, demandsegment.id,)
        ))
    except Exception as e:
        print(e)
        context = {
            'simulation': simulation,
        }
        return render(request, 'metro_app/import_error.html', context)

@owner_required
@check_demand_relation
def matrix_reset(request, simulation, demandsegment):
    """View to reset all OD pairs of an O-D matrix."""
    # Get matrix.
    matrix = demandsegment.matrix
    # Delete matrix points.
    matrix_points = Matrix.objects.filter(matrices=matrix)
    matrix_points.delete()
    # Update total.
    matrix.total = 0
    matrix.save()
    return HttpResponseRedirect(reverse(
        'metro:matrix_main', args=(simulation.id, demandsegment.id,)
    ))

@public_required
@check_demand_relation
def pricing_main(request, simulation, demandsegment):
    """View to display the road pricing main page of an user type."""
    # Get number of tolls.
    count = 0
    # Get links.
    links = get_query('link', simulation)
    has_link = links.count() >= 1
    # Get an import form.
    import_form = ImportForm()
    # Check ownership.
    owner = can_edit(request.user, simulation)
    context = {
        'simulation': simulation,
        'demandsegment': demandsegment,
        'count': count,
        'has_link': has_link,
        'import_form': import_form,
        'owner': owner,
    }
    return render(request, 'metro_app/pricing_main.html', context)

@public_required
@check_demand_relation
def pricing_view(request, simulation, demandsegment):
    """View to display the tolls of an user type."""
    context = {
        'simulation': simulation,
        'demandsegment': demandsegment,
    }
    return render(request, 'metro_app/pricing_view.html', context)

@owner_required
@check_demand_relation
def pricing_edit(request, simulation, demandsegment):
    """View to edit the tolls of an user type."""
    context = {
        'simulation': simulation,
        'demandsegment': demandsegment,
    }
    return render(request, 'metro_app/pricing_edit.html', context)

@require_POST
@owner_required
@check_demand_relation
def pricing_save(request, simulation, demandsegment):
    """View to save the tolls of an user type."""
    return HttpResponseRedirect(reverse(
        'metro:pricing_edit', args=(simulation.id, demandsegment.id,)
    ))

@public_required
@check_demand_relation
def pricing_export(request, simulation, demandsegment):
    """View to send a file with the tolls of an user type."""
    return HttpResponseRedirect(reverse(
        'metro:pricing_main', args=(simulation.id, demandsegment.id,)
    ))

@require_POST
@owner_required
@check_demand_relation
def pricing_import(request, simulation, demandsegment):
    """View to convert the imported file to tolls in the database."""
    return HttpResponseRedirect(reverse(
        'metro:pricing_view', args=(simulation.id, demandsegment.id,)
    ))

@owner_required
@check_demand_relation
def pricing_reset(request, simulation, demandsegment):
    """View to reset the tolls of an user type."""
    return HttpResponseRedirect(reverse(
        'metro:pricing_main', args=(simulation.id, demandsegment.id,)
    ))

@public_required
def public_transit_view(request, simulation):
    """Main view of the public transit system."""
    owner = can_edit(request.user, simulation)
    centroids = get_query('centroid', simulation)
    has_centroid = centroids.exists()
    large_matrix = False
    if has_centroid:
        large_matrix = centroids.count() > MATRIX_THRESHOLD
    public_transit_pairs = get_query('public_transit', simulation)
    is_empty = not public_transit_pairs.exists()
    is_complete = False
    if not is_empty:
        # Public transit system is complete if there is the travel time for all
        # O-D pairs.
        is_complete = (
            public_transit_pairs.count() == (centroids.count() ** 2) 
            - centroids.count()
        )
    import_form = ImportForm()
    context = {
        'simulation': simulation,
        'owner': owner,
        'is_empty': is_empty,
        'is_complete': is_complete,
        'import_form': import_form,
        'has_centroid': has_centroid,
        'large_matrix': large_matrix,
    }
    return render (request, 'metro_app/public_transit_view.html', context)

@public_required
def public_transit_list(request, simulation):
    """View to display the public-transit travel times."""
    centroids = get_query('centroid', simulation)
    if centroids.count() > MATRIX_THRESHOLD:
        # Large matrix, return a table instead.
        return PTMatrixListView.as_view()(request, simulation=simulation)
    else:
        # Small matrix, return it.
        matrix_points = get_query('public_transit', simulation)
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
                    except Matrix.DoesNotExist:
                        row.append(0)
            od_matrix.append(row)
        demandsegment = get_query('demandsegment', simulation)
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
    matrix_points = get_query('public_transit', simulation)
    centroids = get_query('centroid', simulation)
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
    formset = MatrixFormSet(
        queryset=matrix_points.all()
    )
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
    matrix = simulation.scenario.supply.pttimes
    # Get the formset from the POST data and save it.
    formset = MatrixFormSet(request.POST)
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
    """Delete all OD pairs of the public transit OD matrix.

    The Matrices object is not deleted so that the user can add OD pairs again.
    """
    od_pairs = get_query('public_transit', simulation)
    od_pairs.delete()
    return HttpResponseRedirect(reverse(
        'metro:public_transit_view', args=(simulation.id,)
    ))

@require_POST
@owner_required
def public_transit_import(request, simulation):
    """View to convert the imported file to an O-D matrix in the database."""
    try:
        # Create a set with all existing OD pairs in the OD matrix.
        matrix = simulation.scenario.supply.pttimes
        pairs = get_query('public_transit', simulation)
        existing_pairs = set(pairs.values_list('p_id', 'q_id'))
        # Create a dictionary to map the centroid user ids with the centroid
        # objects.
        centroids = get_query('centroid', simulation)
        centroid_mapping = dict()
        centroid_id_mapping = dict()
        for centroid in centroids:
            centroid_mapping[centroid.user_id] = centroid
            centroid_id_mapping[centroid.user_id] = centroid.id
        # Convert the imported file to a csv DictReader.
        encoded_file = request.FILES['import_file']
        tsv_file = StringIO(encoded_file.read().decode())
        reader = csv.DictReader(tsv_file, delimiter='\t')
        # For each imported OD pair, if the pair already exists in the OD Matrix,
        # it is stored to be updated, else it is stored to be created.
        to_be_updated = set()
        to_be_created = list()
        for row in reader:
            pair = (
                centroid_id_mapping[int(row['origin'])],
                centroid_id_mapping[int(row['destination'])]
            )
            if pair in existing_pairs:
                to_be_updated.add((*pair, float(row['travel time'])))
            else:
                to_be_created.append(
                    Matrix(p=centroid_mapping[int(row['origin'])],
                           q=centroid_mapping[int(row['destination'])],
                           r=float(row['travel time']),
                           matrices=matrix)
                )
        if to_be_updated:
            # Create a mapping between the values (p, q, r) and the ids.
            pair_values = set(pairs.values_list('id', 'p_id', 'q_id'))
            pair_mapping = dict()
            for pair in pair_values:
                pair_mapping[pair[1:]] = pair[0]
            # Find the pairs that really need to be updated (i.e. r is also
            # different).
            pair_values = set(pairs.values_list('p_id', 'q_id', 'r'))
            to_be_updated = to_be_updated.difference(pair_values)
            # Retrieve the ids of the pairs to be updated with the mapping and
            # delete them.
            to_be_updated_ids = [pair_mapping[pair[:2]] for pair in to_be_updated]
            with connection.cursor() as cursor:
                chunk_size = 20000
                chunks = [to_be_updated_ids[x:x+chunk_size]
                          for x in range(0, len(to_be_updated_ids), chunk_size)]
                for chunk in chunks:
                    cursor.execute(
                        "DELETE FROM Matrix "
                        "WHERE id IN %s;",
                        [chunk]
                    )
            # Create a mapping between the centroids ids and the centroid objects.
            centroid_id_mapping = dict()
            for centroid in centroids:
                centroid_id_mapping[centroid.id] = centroid
            # Now, create the updated pairs with the new values.
            to_be_created += [
                Matrix(p=centroid_id_mapping[pair[0]],
                       q=centroid_id_mapping[pair[1]],
                       r=pair[2],
                       matrices=matrix)
                for pair in to_be_updated
            ]
        # Create the new OD pairs in bulk.
        # The chunk size is limited by the MySQL engine (timeout if it is too big).
        chunk_size = 20000
        chunks = [to_be_created[x:x+chunk_size] 
                  for x in range(0, len(to_be_created), chunk_size)]
        for chunk in chunks:
            Matrix.objects.bulk_create(chunk, chunk_size)
        return HttpResponseRedirect(reverse(
            'metro:public_transit_view', args=(simulation.id,)
        ))
    except Exception as e:
        print(e)
        context = {
            'simulation': simulation,
        }
        return render(request, 'metro_app/import_error.html', context)

@public_required
def public_transit_export(request, simulation):
    """View to send a file with the public transit OD Matrix to the user."""
    matrix_couples = get_query('public_transit', simulation)
    # To avoid conflict if two users export a file at the same time, we
    # generate a random name for the export file.
    seed = np.random.randint(10000)
    filename = '{0}/website_files/exports/{1}.tsv'.format(settings.BASE_DIR,
                                                          seed)
    with codecs.open(filename, 'w', encoding='utf8') as f:
        writer = csv.writer(f, delimiter='\t')
        # Get a dictionary with all the values to export.
        values = matrix_couples.values_list('p__user_id', 'q__user_id', 'r')
        # Write a custom header.
        writer.writerow(['origin', 'destination', 'travel time'])
        writer.writerows(values)
    with codecs.open(filename, 'r', encoding='utf8') as f:
        # Build a response to send a file.
        response = HttpResponse(f.read())
        response['content_type'] = 'text/tab-separated-values'
        response['Content-Disposition'] = 'attachement; filename=pttimes.tsv'
    # We delete the export file to save disk space.
    os.remove(filename)
    return response

@public_required
def object_view(request, simulation, object):
    """Main view of a network object."""
    owner = can_edit(request.user, simulation)
    query = get_query(object, simulation)
    large_count = query.count() > OBJECT_THRESHOLD
    network_empty = False
    if object == 'link':
        #Allow the user to edit links only if there are at least two centroids,
        # one crossing and one congestion function.
        nb_centroids = get_query('centroid', simulation).count()
        nb_crossings = get_query('crossing', simulation).count()
        nb_functions = get_query('function', simulation).count()
        network_empty = not (nb_centroids >= 2 and nb_crossings >= 1
                             and nb_functions >= 1)
    import_form = ImportForm()
    context = {
        'simulation': simulation,
        'owner': owner,
        'count': query.count(),
        'object': object,
        'large_count': large_count,
        'network_empty': network_empty,
        'import_form': import_form,
    }
    return render(request, 'metro_app/object_view.html', context)

@public_required
def object_list(request, simulation, object):
    """View to list all instances of a network object."""
    if object == 'centroid':
        return CentroidListView.as_view()(request, simulation=simulation)
    elif object == 'crossing':
        return CrossingListView.as_view()(request, simulation=simulation)
    elif object == 'link':
        return LinkListView.as_view()(request, simulation=simulation)
    elif object == 'function':
        return FunctionListView.as_view()(request, simulation=simulation)
    else:
        return Http404()

@owner_required
def object_edit(request, simulation, object):
    """View to edit all instances of a network object."""
    formset = gen_formset(object, simulation)
    context = {
        'simulation': simulation,
        'object': object,
        'formset': formset,
    }
    return render(request, 'metro_app/object_edit.html', context)

@require_POST
@owner_required
def object_edit_save(request, simulation, object):
    """View to save the edited network objects."""
    # Retrieve the formset from the POST data.
    formset = gen_formset(object, simulation, request=request)
    if formset.is_valid():
        formset.save()
        # Update the foreign keys (we cannot select the newly added forms so we
        # do it for all forms not deleted).
        changed_forms = list(
            set(formset.forms) - set(formset.deleted_forms)
        )
        if object in ['centroid', 'crossing', 'link']:
            for form in changed_forms:
                form.instance.network.add(
                    simulation.scenario.supply.network
                )
        elif object == 'function':
            for form in changed_forms:
                form.vdf_id = form.instance.id
                form.save()
                form.instance.functionset.add(
                    simulation.scenario.supply.functionset
                )
        simulation.has_changed = True
        simulation.save()
        return HttpResponseRedirect(reverse(
            'metro:object_edit', args=(simulation.id, object,)
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
def object_import(request, simulation, object):
    """View to import instances of a network object.

    This view could be much more simple but I tried to use as little as
    possible Django ORM (the querysets) to speed up the view.
    Basically, this view looks at each row in the imported file to find if an
    instance already exists for the row (user_id already used) or if a new
    instance needs to be created. If the instance already exists, the view
    compares the values in the file with the values in the database to know if
    the instance needs to be updated.
    Python built-in set are used to perform comparison of arrays quickly.
    """
    try:
        if object == 'function':
            parent = simulation.scenario.supply.functionset
        else:
            parent = simulation.scenario.supply.network
        query = get_query(object, simulation)
        user_id_set = set(query.values_list('user_id', flat=True))
        if object == 'link':
            # To import links, we retrieve the user ids of all centroids, crossings
            # and functions and we build mappings between ids and objects.
            centroids = get_query('centroid', simulation)
            centroid_ids = set(centroids.values_list('user_id', flat=True))
            crossings = get_query('crossing', simulation)
            crossing_ids = set(crossings.values_list('user_id', flat=True))
            node_ids = centroid_ids.union(crossing_ids)
            # Mapping between the user id and the id of the nodes.
            node_mapping = dict()
            for centroid in centroids:
                node_mapping[centroid.user_id] = centroid.id
            for crossing in crossings:
                node_mapping[crossing.user_id] = crossing.id
            functions = get_query('function', simulation)
            function_ids = set(functions.values_list('user_id', flat=True))
            # Mapping between the user id and the id of the functions.
            function_id_mapping = dict()
            # Mapping between the user id and the instance of the functions
            function_mapping = dict()
            for function in functions:
                function_id_mapping[function.user_id] = function.id
                function_mapping[function.user_id] = function
        # Convert imported file to a csv DictReader.
        encoded_file = request.FILES['import_file']
        tsv_file = StringIO(encoded_file.read().decode())
        reader = csv.DictReader(tsv_file, delimiter='\t')
        to_be_updated = set()
        to_be_created = list()
        # Store the user_id of the imported instance to avoid two instances
        # with the same id.
        imported_ids = set()
        if object == 'centroid':
            # Do not import centroid with same id as a crossing.
            crossings = get_query('crossing', simulation)
            imported_ids = set(crossings.values_list('user_id', flat=True))
            for row in reader:
                id = int(row['id'])
                if not id in imported_ids:
                    imported_ids.add(id)
                    if id in user_id_set:
                        to_be_updated.add(
                            (id, row['name'], float(row['x']),
                             float(row['y']))
                        )
                    else:
                        to_be_created.append(
                            Centroid(user_id=id, name=row['name'],
                                     x=float(row['x']), y=float(row['y']))
                        )
        elif object == 'crossing':
            # Do not import crossing with same id as a centroid.
            centroids = get_query('centroid', simulation)
            imported_ids = set(centroids.values_list('user_id', flat=True))
            for row in reader:
                id = int(row['id'])
                if not id in imported_ids:
                    imported_ids.add(id)
                    if id in user_id_set:
                        to_be_updated.add(
                            (id, row['name'], float(row['x']),
                             float(row['y']))
                        )
                    else:
                        to_be_created.append(
                            Crossing(user_id=id, name=row['name'],
                                     x=float(row['x']), y=float(row['y']))
                        )
        elif object == 'function':
            for row in reader:
                id = int(row['id'])
                if not id in imported_ids:
                    imported_ids.add(id)
                    if id in user_id_set:
                        to_be_updated.add(
                            (id, row['name'], row['expression'])
                        )
                    else:
                        to_be_created.append(
                            Function(user_id=id, name=row['name'],
                                     expression=row['expression'])
                        )
        elif object == 'link':
            for row in reader:
                id = int(row['id'])
                if not id in imported_ids:
                    imported_ids.add(id)
                    if id in user_id_set:
                        to_be_updated.add(
                            (id, row['name'],
                             node_mapping[int(row['origin'])],
                             node_mapping[int(row['destination'])], 
                             function_id_mapping[int(row['function'])],
                             float(row['lanes']), float(row['length']),
                             float(row['speed']), float(row['capacity']))
                        )
                    else:
                        if int(row['origin']) in node_ids \
                                and int(row['destination']) in node_ids \
                                and int(row['function']) in function_ids:
                            # Ignore the links with unidentified origin,
                            # destination or function.
                            to_be_created.append(
                                Link(user_id=id, name=row['name'],
                                     origin=node_mapping[int(row['origin'])],
                                     destination=node_mapping[int(row['destination'])],
                                     vdf=function_mapping[int(row['function'])],
                                     lanes=float(row['lanes']),
                                     length=float(row['length']),
                                     speed=float(row['speed']),
                                     capacity=float(row['capacity']))
                            )
        if to_be_updated:
            if object in ('centroid', 'crossing'):
                values = set(query.values_list('user_id', 'name', 'x', 'y'))
            elif object == 'function':
                values = set(query.values_list('user_id', 'name', 'expression'))
            elif object == 'link':
                values = set(query.values_list('user_id', 'name', 'origin',
                                                'destination', 'vdf_id', 'lanes',
                                                'length', 'speed', 'capacity'))
            # Find the instances that really need to be updated (the values have
            # changed).
            to_be_updated = to_be_updated.difference(values)
            if object in ('centroid', 'crossing', 'function'):
                # Update the objects (it would be faster to delete and re-create
                # them but this would require to also change the foreign keys of
                # the links).
                for values in to_be_updated:
                    # Index 0 of values is the id column i.e. the user_id.
                    instance = query.filter(user_id=values[0])
                    if object in ('centroid', 'crossing'):
                        instance.update(name=values[1], x=values[2], y=values[3])
                    else: # Function
                        instance.update(name=values[1], expression=values[2])
            elif object == 'link':
                # Delete the links and re-create them.
                ids = list(query.values_list('id', 'user_id'))
                # Create a mapping between the user ids and the ids.
                id_mapping = dict()
                for i in range(len(values)):
                    id_mapping[ids[i][1]] = ids[i][0]
                # Retrieve the ids of the links to be updated with the mapping and
                # delete them.
                to_be_updated_ids = [id_mapping[values[0]]
                                     for values in to_be_updated]
                with connection.cursor() as cursor:
                    chunk_size = 20000
                    chunks = [
                        to_be_updated_ids[x:x+chunk_size]
                        for x in range(0, len(to_be_updated_ids), chunk_size)
                    ]
                    for chunk in chunks:
                        # Delete the relations first.
                        cursor.execute(
                            "DELETE FROM Network_Link "
                            "WHERE link_id IN %s;",
                            [chunk]
                        )
                        cursor.execute(
                            "DELETE FROM Link "
                            "WHERE id IN %s;",
                            [chunk]
                        )
                # Create a mapping between the id and the instance of the
                # functions.
                function_mapping = dict()
                for function in functions:
                    function_mapping[function.id] = function
                # Now, create the updated instances with the new values.
                to_be_created += [
                    Link(user_id=values[0], name=values[1], origin=values[2],
                         destination=values[3], vdf=function_mapping[values[4]],
                         lanes=values[5], length=values[6], speed=values[7],
                         capacity=values[8])
                    for values in to_be_updated
                ]
        # Create the new objects in bulk.
        # The chunk size is limited by the MySQL engine (timeout if it is too big).
        chunk_size = 10000
        chunks = [to_be_created[x:x+chunk_size] 
                  for x in range(0, len(to_be_created), chunk_size)]
        # Remove the orphan instances.
        if object == 'function':
            query.model.objects \
                .exclude(functionset__in=FunctionSet.objects.all()) \
                .delete()
        else:
            query.model.objects.exclude(network__in=Network.objects.all()).delete()
        for chunk in chunks:
            # Create the new instances.
            query.model.objects.bulk_create(chunk, chunk_size)
            # Retrieve the newly created instances and add the many-to-many
            # relation.
            # Add the many-to-many relation.
            if object == 'function':
                new_instances = query.model.objects \
                    .exclude(functionset__in=FunctionSet.objects.all())
                for instance in new_instances:
                    instance.functionset.add(parent)
            else:
                new_instances = query.model.objects \
                    .exclude(network__in=Network.objects.all())
                for instance in new_instances:
                    instance.network.add(parent)
        simulation.has_changed = True
        simulation.save()
        return HttpResponseRedirect(
            reverse('metro:object_list', args=(simulation.id, object,))
        )
    except Exception as e:
        print(e)
        context = {
            'simulation': simulation,
        }
        return render(request, 'metro_app/import_error.html', context)

@public_required
def object_export(request, simulation, object):
    """View to export all instances of a network object."""
    query = get_query(object, simulation)
    # To avoid conflict if two users export a file at the same time, we
    # generate a random name for the export file.
    seed = np.random.randint(10000)
    filename = '{0}/website_files/exports/{1}.tsv'.format(settings.BASE_DIR,
                                                          seed)
    with codecs.open(filename, 'w', encoding='utf8') as f:
        if object == 'centroid':
            fields = ['id', 'name', 'x', 'y', 'db_id']
        elif object == 'crossing':
            fields = ['id', 'name', 'x', 'y', 'db_id']
        elif object == 'link':
            fields = ['id', 'name', 'origin', 'destination', 'lanes', 'length',
                      'speed', 'capacity', 'vdf']
        elif object == 'function':
            fields = ['id', 'expression']
        writer = csv.writer(f, delimiter='\t')
        if object in ('centroid', 'crossing'):
            writer.writerow(['id', 'name', 'x', 'y', 'db_id'])
            values = query.values_list('user_id', 'name', 'x', 'y', 'id')
        elif object == 'function':
            writer.writerow(['id', 'expression'])
            values = query.values_list('user_id', 'expression')
        elif object == 'link':
            writer.writerow(['id', 'name', 'lanes', 'length', 'speed',
                             'capacity', 'function', 'origin', 'destination'])
            values = query.values_list('user_id', 'name', 'lanes', 'length',
                                       'speed', 'capacity', 'vdf__user_id')
            # Origin and destination id must be converted to user_id.
            centroids = get_query('centroid', simulation)
            crossings = get_query('crossing', simulation)
            ids = list(centroids.values_list('id', 'user_id'))
            ids += list(crossings.values_list('id', 'user_id'))
            # Map id of nodes to their user_id.
            id_mapping = dict(ids)
            origins = query.values_list('origin', flat=True)
            origins = np.array([id_mapping[n] for n in origins])
            destinations = query.values_list('destination', flat=True)
            destinations = np.array([id_mapping[n] for n in destinations])
            # Add origin and destination user ids to the values array.
            origins = np.transpose([origins])
            destinations = np.transpose([destinations])
            values = np.hstack([values, origins, destinations])
        writer.writerows(values)
    with codecs.open(filename, 'r', encoding='utf8') as f:
        # Build a response to send a file.
        response = HttpResponse(f.read())
        response['content_type'] = 'text/tab-separated-values'
        response['Content-Disposition'] = \
            'attachement; filename={}.tsv'.format(metro_to_user(object))
    # We delete the export file to save disk space.
    os.remove(filename)
    return response

@owner_required
def object_delete(request, simulation, object):
    """View to delete all instances of a network objects."""
    query = get_query(object, simulation)
    query.delete()
    simulation.has_changed = True
    simulation.save()
    return HttpResponseRedirect(reverse(
        'metro:object_view', args=(simulation.id, object,)
    ))

@require_POST
@owner_required
def simulation_run_action(request, simulation):
    """View to create a new SimulationRun and launch the simulation."""
    # Check that there is no run in progress for this simulation.
    running_simulations = SimulationRun.objects.filter(
        simulation=simulation
    ).filter(status__in=('Preparing', 'Running', 'Ending'))
    if not running_simulations.exists():
        # Create a SimulationRun object to keep track of the run.
        run_form = RunForm(request.POST)
        if run_form.is_valid():
            run = run_form.save(simulation)
            run_simulation(run)
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
    results = SimulationMOEs.objects.filter(runid=run.id).order_by('-day')
    result_table = SimulationMOEsTable(results)
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
    runs = get_query('run', simulation).order_by('-id')
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
        db_name = settings.DATABASES['default']['NAME']
        file_path = (
            '{0}/website_files/network_output/link_results_{1}_{2}.txt'
            .format(settings.BASE_DIR, simulation.id, run.id)
        )
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
        db_name = settings.DATABASES['default']['NAME']
        file_path = (
            '{0}/website_files/network_output/user_results_{1}_{2}.txt'
            .format(settings.BASE_DIR, simulation.id, run.id)
        )
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
def network_view(request, simulation):
    """View of the network of a simulation."""
    # If the network is large, the display method is different.
    links = get_query('link', simulation)
    large_network = links.count() > NETWORK_THRESHOLD
    # File where the data for the network are stored.
    output_file = (
        '{0}/website_files/network_output/network_{1!s}.json'
        .format(settings.BASE_DIR, simulation.id)
    )
    if simulation.has_changed or not os.path.isfile(output_file):
        # Generate a new output file.
        output = network_output(simulation, large_network)
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

@public_required
@check_run_relation
def network_view_run(request, simulation, run):
    """View of the network of a simulation with the disaggregated results of a
    specific run.
    """
    # If the network is large, the display method is different.
    links = get_query('link', simulation)
    large_network = links.count() > NETWORK_THRESHOLD
    # Files where the data for the network are stored.
    network_file = (
        '{0}/website_files/network_output/network_{1}_{2}.json'
        .format(settings.BASE_DIR, simulation.id, run.id)
    )
    parameters_file = (
        '{0}/website_files/network_output/parameters_{1}_{2}.json'
        .format(settings.BASE_DIR, simulation.id, run.id)
    )
    results_file = (
        '{0}/website_files/network_output/results_{1}_{2}.json'
        .format(settings.BASE_DIR, simulation.id, run.id)
    )
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


#====================
# Class-Based Views
#====================

class MatrixListView(SingleTableMixin, FilterView):
    """Class-based view to show an OD Matrix as a table.

    The class must be initiated with one positional argument, the request, and
    two keyword arguments, simulation and demandsegment.
    """
    table_class = MatrixTable
    model = Matrix
    template_name = 'metro_app/matrix_list.html'
    filterset_class = MatrixFilter
    paginate_by = 25
    # With django-filters 2.0, strict = False is required to show the queryset
    # when no filter is active.
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        self.demandsegment = self.kwargs['demandsegment']
        queryset = Matrix.objects.filter(matrices=self.demandsegment.matrix)
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
    table_class = PTMatrixTable
    model = Matrix
    template_name = 'metro_app/matrix_list.html'
    filterset_class = PTMatrixFilter
    paginate_by = 25
    # With django-filters 2.0, strict = False is required to show the queryset
    # when no filter is active.
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = get_query('public_transit', self.simulation)
        return queryset

    def get_context_data(self, **kwargs):
        context = super(PTMatrixListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['public_transit'] = True
        return context

class CentroidListView(SingleTableMixin, FilterView):
    table_class = CentroidTable
    model = Centroid
    template_name = 'metro_app/object_list.html'
    filterset_class = CentroidFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = get_query('centroid', self.simulation).order_by('user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(CentroidListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['object'] = 'centroid'
        return context

class CrossingListView(SingleTableMixin, FilterView):
    table_class = CrossingTable
    model = Crossing
    template_name = 'metro_app/object_list.html'
    filterset_class = CrossingFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = get_query('crossing', self.simulation).order_by('user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(CrossingListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['object'] = 'crossing'
        return context

class LinkListView(SingleTableMixin, FilterView):
    table_class = LinkTable
    model = Link
    template_name = 'metro_app/object_list.html'
    filterset_class = LinkFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = get_query('link', self.simulation).order_by('user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(LinkListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['object'] = 'link'
        return context

class FunctionListView(SingleTableMixin, FilterView):
    table_class = FunctionTable
    model = Function
    template_name = 'metro_app/object_list.html'
    filterset_class = FunctionFilter
    paginate_by = 25
    strict = False

    def get_queryset(self):
        self.simulation = self.kwargs['simulation']
        queryset = get_query('function', self.simulation).order_by('user_id')
        return queryset

    def get_context_data(self, **kwargs):
        context = super(FunctionListView, self).get_context_data(**kwargs)
        context['simulation'] = self.simulation
        context['object'] = 'function'
        return context


#====================
# Receivers
#====================

@receiver(pre_delete, sender=FunctionSet)
def pre_delete_function_set(sender, instance, **kwargs):
    """Delete all objects related to a functionset before deleting the
    functionset.
    """
    # Delete all functions (this also deletes the links).
    instance.function_set.all().delete()

@receiver(pre_delete, sender=Network)
def pre_delete_network(sender, instance, **kwargs):
    """Delete all objects related to a network before deleting the network.
    
    The links are deleted when the functions are deleted.
    """
    # Disable the pre_delete signal for centroids (the signal is useless
    # because the links are already deleted but it slows down the deleting
    # process).
    pre_delete.disconnect(sender=Centroid, dispatch_uid="centroid")
    instance.centroid_set.all().delete()
    # Enable the pre_delete signal again.
    pre_delete.connect(pre_delete_centroid, sender=Centroid)
    pre_delete.disconnect(sender=Crossing, dispatch_uid="crossing")
    instance.crossing_set.all().delete()
    pre_delete.connect(pre_delete_crossing, sender=Crossing)

@receiver(pre_delete, sender=Centroid, dispatch_uid="centroid")
def pre_delete_centroid(sender, instance, **kwargs):
    """Delete all links related to a centroid before deleting the centroid.
    
    The signal should not be activated when deleting the whole simulation
    because the links are already deleted when deleting the centroids so it
    slows down the deleting process.
    """
    Link.objects.filter(origin=instance.id).delete()
    Link.objects.filter(destination=instance.id).delete()

@receiver(pre_delete, sender=Crossing, dispatch_uid="crossing")
def pre_delete_crossing(sender, instance, **kwargs):
    """Delete all links related to a crossing before deleting the crossing."""
    Link.objects.filter(origin=instance.id).delete()
    Link.objects.filter(destination=instance.id).delete()

@receiver(pre_delete, sender=Demand)
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


#====================
# Functions
#====================

def run_simulation(run):
    """Function to start a SimulationRun.

    This function writes the argument file of Metropolis, then runs two scripts
    and Metrosim.
    """
    # Write the argument file used by metrosim.
    simulation = run.simulation
    metrosim_dir = settings.BASE_DIR + '/metrosim_files/'
    metrosim_file = '{0}execs/metrosim'.format(metrosim_dir)
    arg_file = (
        '{0}arg_files/simulation_{1!s}_run_{2!s}.txt'.format(metrosim_dir, 
                                                             simulation.id, 
                                                             run.id)
    )
    with open(arg_file, 'w') as f:
        database = settings.DATABASES['default']
        db_host = database['HOST']
        db_name = database['NAME']
        db_user = database['USER']
        db_pass = database['PASSWORD']
        log = metrosim_dir + 'logs/run_{}.txt'.format(run.id)
        tmp = metrosim_dir + 'output'
        stop = metrosim_dir + 'stop_files/run_{}.stop'.format(run.id)
        arguments = ('-dbHost "{0}" -dbName "{1}" -dbUser "{2}" '
                     + '-dbPass "{3}" -logFile "{4}" -tmpDir "{5}" '
                     + '-stopFile "{6}" -simId "{7!s}" -runId "{8!s}"'
                     ).format(db_host, db_name, db_user, db_pass, log, tmp,
                              stop, simulation.id, run.id)
        f.write(arguments)

    # Run the script 'prepare_run.py' then run metrosim then run the script 
    # 'run_end.py'.
    # The two scripts are run with the run.id as an argument.
    prepare_run_file = settings.BASE_DIR + '/metro_app/prepare_run.py'
    build_results_file = settings.BASE_DIR + '/metro_app/build_results.py'
    log_file = (
        '{0}/website_files/script_logs/run_{1}.txt'.format(
            settings.BASE_DIR, run.id
        )
    )
    # Command looks like: 
    #
    # python3 ./metro_app/prepare_results.py y
    # > ./website_files/script_logs/run_y.txt
    # && ./metrosim_files/execs/metrosim
    # ./metrosim_files/arg_files/simulation_x_run_y.txt 
    # && python3 ./metro_app/build_results.py y 
    # > ./website_files/script_logs/run_y.txt
    #
    command = ('python3 {first_script} {run_id} > {log} && {metrosim} '
               + '{argfile} && python3 {second_script} {run_id} > {log}')
    command = command.format(first_script=prepare_run_file, run_id=run.id,
                             log=log_file, metrosim=metrosim_file,
                             argfile=arg_file,
                             second_script=build_results_file)
    subprocess.Popen(command, shell=True)

def gen_formset(object_name, simulation, request=None):
    """Function to generate a formset either from a simulation object or from a
    request object.

    If there is no existing instance of the object, create a formset with an
    empty form (it is impossible to add the first form otherwise).
    """
    formset = None
    query = get_query(object_name, simulation)
    if object_name == 'centroid':
        if request:
            if query.exists():
                formset = CentroidFormSet(
                    request.POST,
                    prefix='centroid',
                    simulation=simulation,
                )
            else:
                formset = CentroidFormSetExtra(
                    request.POST,
                    prefix='centroid',
                    simulation=simulation,
                )
        else:
            if query.exists():
                formset = CentroidFormSet(
                    queryset=query,
                    prefix='centroid',
                    simulation=simulation,
                )
            else:
                formset = CentroidFormSetExtra(
                    queryset=query,
                    prefix='centroid',
                    simulation=simulation,
                )
    elif object_name == 'crossing':
        if request:
            if query.exists():
                formset = CrossingFormSet(
                    request.POST,
                    prefix='crossing',
                    simulation=simulation,
                )
            else:
                formset = CrossingFormSetExtra(
                    request.POST,
                    prefix='crossing',
                    simulation=simulation,
                )
        else:
            if query.exists():
                formset = CrossingFormSet(
                    queryset=query,
                    prefix='crossing',
                    simulation=simulation,
                )
            else:
                formset = CrossingFormSetExtra(
                    queryset=query,
                    prefix='crossing',
                    simulation=simulation,
                )
    elif object_name == 'link':
        if request:
            if query.exists():
                formset = LinkFormSet(
                    request.POST,
                    prefix='link',
                    simulation=simulation,
                    form_kwargs={'simulation': simulation},
                )
            else:
                formset = LinkFormSetExtra(
                    request.POST,
                    prefix='link',
                    simulation=simulation,
                    form_kwargs={'simulation': simulation},
                )
        else:
            if query.exists():
                formset = LinkFormSet(
                    queryset=query,
                    prefix='link',
                    simulation=simulation,
                    form_kwargs={'simulation': simulation}
                )
            else:
                formset = LinkFormSetExtra(
                    queryset=query,
                    prefix='link',
                    simulation=simulation,
                    form_kwargs={'simulation': simulation}
                )
    elif object_name == 'function':
        if request:
            if query.exists():
                formset = FunctionFormSet(
                    request.POST,
                    prefix='function',
                    simulation=simulation,
                )
            else:
                formset = FunctionFormSetExtra(
                    request.POST,
                    prefix='function',
                    simulation=simulation,
                )
        else:
            if query.exists():
                formset = FunctionFormSet(
                    queryset=query,
                    prefix='function',
                    simulation=simulation,
                )
            else:
                formset = FunctionFormSetExtra(
                    queryset=query,
                    prefix='function',
                    simulation=simulation,
                )
    return formset
