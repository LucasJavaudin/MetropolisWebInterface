#!/usr/bin/env python
"""This file defines functions used by the other files.

Author: Lucas Javaudin
E-mail: lucas.javaudin@ens-paris-saclay.fr
"""

import os
import csv
from io import StringIO

from django.conf import settings

from .models import *

def get_query(object_name, simulation):
    """Function used to return all instances of an object related to a
    simulation.
    """
    query = None
    if object_name == 'centroid':
        query = Centroid.objects.filter(
            network__supply__scenario__simulation=simulation
        )
    elif object_name == 'crossing':
        query = Crossing.objects.filter(
            network__supply__scenario__simulation=simulation
        )
    elif object_name == 'link':
        query = Link.objects.filter(
            network__supply__scenario__simulation=simulation
        )
    elif object_name == 'function':
        query = Function.objects.filter(
            functionset__supply__scenario__simulation=simulation
        )
    elif object_name == 'usertype':
        query = UserType.objects.filter(
            demandsegment__demand__scenario__simulation=simulation
        )
    elif object_name == 'demandsegment':
        query = DemandSegment.objects.filter(
            demand__scenario__simulation=simulation
        )
    elif object_name == 'matrices':
        query = Matrices.objects.filter(
            demandsegment__demand__scenario__simulation=simulation
        )
    elif object_name == 'run':
        query = SimulationRun.objects.filter(
            simulation=simulation
        )
    elif object_name == 'public_transit':
        if simulation.scenario.supply.pttimes: # Variable pttimes can be null.
            query = Matrix.objects.filter(
                matrices=simulation.scenario.supply.pttimes
            )
    elif object_name == 'policy':
        query = Policy.objects.filter(scenario=simulation.scenario)
    return query

def can_view(user, simulation):
    """Check if the user can view a specific simulation.

    The user can view the simulation if the simulation is public, if he owns
    the simulation or if he is a superuser.
    """
    if simulation.public or simulation.user == user or user.is_superuser:
        return True
    else:
        return False

def can_edit(user, simulation):
    """Check if the user can edit a specific simulation.

    The user can edit the simulation if he owns the simulation or if he is a
    superuser.
    """
    if simulation.user == user or user.is_superuser:
        return True
    else:
        return False

def metro_to_user(object):
    """Convert the name of a network object (used in the source code) to a name
    suitable for users.
    """
    if object == 'centroid':
        return 'zone'
    elif object == 'crossing':
        return 'intersection'
    elif object == 'link':
        return 'link'
    elif object == 'function':
        return 'congestion function'
    return ''

def custom_check_test(value):
    """Custom check_test to convert metropolis string booleans into Python
    booleans.
    """
    if value == 'true':
        return True
    else:
        return False

def get_node_choices(simulation):
    """Return all the nodes (centroids and crossings) related to a simulation.

    These nodes can be origin or destination of links.
    """
    centroids = Centroid.objects.filter(
            network__supply__scenario__simulation=simulation
    )
    crossings = Crossing.objects.filter(
            network__supply__scenario__simulation=simulation
    )
    centroid_choices = [(centroid.id, str(centroid)) for centroid in centroids]
    crossing_choices = [(crossing.id, str(crossing)) for crossing in crossings]
    node_choices = centroid_choices + crossing_choices
    return node_choices

def convert_to_metro_matrix(matrice_id, centroid_id_map):
    """Convert an od matrix file using user_id to an od matrix file using
    database id.
    """
    path = (
        '{0}/website_files/network_output/od_matrix_{1}.tsv'
        .format(settings.BASE_DIR, matrice_id)
    )
    new_path = (
        '{0}/website_files/network_output/od_matrix_clean_{1}.tsv'
        .format(settings.BASE_DIR, matrice_id)
    )
    if os.path.isfile(path):
        with open(path, 'r') as f:
            reader = csv.DictReader(StringIO(f.read()), delimiter='\t')
            values = list()
            for row in reader:
                try:
                    print(row)
                    values.append([
                        centroid_id_map[int(row['origin'])],
                        centroid_id_map[int(row['destination'])],
                        float(row['population']),
                    ])
                except Exception as e:
                    # There was probably an invalid id in the file.
                    print(
                        'Invalid id in file: {0}, {1}'
                        .format(row['origin'], row['destination'])
                    )
        with open(new_path, 'w', encoding='utf8') as g:
            writer = csv.writer(g, delimiter='\t')
            writer.writerow(['p', 'q', 'r'])
            writer.writerows(values)
        print('Converted matrice {} succesfuly'.format(matrice_id))
        return True
    else:
        print('Could not find file "{}"'.format(path))
        return False
