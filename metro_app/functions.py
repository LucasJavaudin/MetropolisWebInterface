#!/usr/bin/env python
"""This file defines functions used by the other files.

Author: Lucas Javaudin
E-mail: lucas.javaudin@ens-paris-saclay.fr
"""

import os
import sys
import subprocess
import re
import csv
from io import StringIO
import codecs
import zipfile
import numpy as np
import pandas as pd

from django.conf import settings
from django.contrib.sessions.backends import file
from django.db.models import Sum
from django.db import connection

from metro_app import models



def get_query(object_name, simulation):
    """Function used to return all instances of an object related to a
    simulation.
    """
    query = None
    if object_name == 'centroid':
        query = models.Centroid.objects.filter(
            network__supply__scenario__simulation=simulation
        )
    elif object_name == 'crossing':
        query = models.Crossing.objects.filter(
            network__supply__scenario__simulation=simulation
        )
    elif object_name == 'link':
        query = models.Link.objects.filter(
            network__supply__scenario__simulation=simulation
        )
    elif object_name == 'function':
        query = models.Function.objects.filter(
            functionset__supply__scenario__simulation=simulation
        )
    elif object_name == 'usertype':
        query = models.UserType.objects.filter(
            demandsegment__demand__scenario__simulation=simulation
        ).order_by('user_id')
    elif object_name == 'demandsegment':
        query = models.DemandSegment.objects.filter(
            demand__scenario__simulation=simulation
        )
    elif object_name == 'matrices':
        query = models.Matrices.objects.filter(
            demandsegment__demand__scenario__simulation=simulation
        )
    elif object_name == 'run':
        query = models.SimulationRun.objects.filter(
            simulation=simulation
        )
    elif object_name == 'public_transit':
        if simulation.scenario.supply.pttimes:  # Variable pttimes can be null.
            query = models.Matrix.objects.filter(
                matrices=simulation.scenario.supply.pttimes
            )
    elif object_name == 'policy':
        query = models.Policy.objects.filter(scenario=simulation.scenario)
    elif object_name == 'batch':
        query = models.Batch.objects.filter(simulation=simulation)
    return query

def get_batch_query(object_name, run):
    """Function used to return all instances of an object related to a
    simulation.
    """
    query = None
    if object_name == 'batch':
        query = models.BatchRun.objects.filter(run=run)
    return query

def can_view(user, simulation):
    """Check if the user can view a specific simulation.

    The user can view the simulation if the simulation is public, if he owns
    the simulation or if he is a superuser.
    """
    env_users = None
    if simulation.environment is not None:
        env_users = simulation.environment.users.all().filter(id=user.id)

    if simulation.public or simulation.user == user or user.is_superuser or \
            env_users:
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


def can_edit_environment(user, environment):
    """Check if the user can edit a specific environment.
    """
    if environment.creator == user or user.is_superuser:
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
    centroids = models.Centroid.objects.filter(
        network__supply__scenario__simulation=simulation
    )
    crossings = models.Crossing.objects.filter(
        network__supply__scenario__simulation=simulation
    )
    centroid_choices = [(centroid.id, str(centroid)) for centroid in centroids]
    crossing_choices = [(crossing.id, str(crossing)) for crossing in crossings]
    node_choices = centroid_choices + crossing_choices
    return node_choices


def run_simulation(run, background=True):
    """Function to start a SimulationRun.

    This function writes the argument file of Metropolis, then runs two scripts
    and Metrosim.
    """
    # Write the argument file used by metrosim.
    simulation = run.simulation
    metrosim_dir = settings.BASE_DIR + '/metrosim_files/'
    metrosim_file = '{0}execs/metrosim.py'.format(metrosim_dir)
    arg_file = (
        '{0}arg_files/simulation_{1!s}_run_{2!s}.txt'
    ).format(metrosim_dir, simulation.id, run.id)
    with open(arg_file, 'w') as f:
        database = settings.DATABASES['default']
        db_host = database['HOST']
        db_name = database['NAME']
        db_user = database['USER']
        db_pass = database['PASSWORD']
        log = metrosim_dir + 'logs/run_{}.txt'.format(run.id)
        tmp = metrosim_dir + 'output'
        stop = metrosim_dir + 'stop_files/run_{}.stop'.format(run.id)
        if simulation.random_seed_check:
            random_seed = simulation.random_seed
        else:
            random_seed = -1
        arguments = (
            '-dbHost "{0}" -dbName "{1}" -dbUser "{2}" -dbPass "{3}" '
            '-logFile "{4}" -tmpDir "{5}" -stopFile "{6}" -simId "{7!s}" '
            '-runId "{8!s}" -randomSeed "{9!s}"'
        ).format(
            db_host, db_name, db_user, db_pass,log, tmp, stop, simulation.id,
            run.id, random_seed)
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
    # python3 ./metro_app/prepare_results.py y &&
    # ./metrosim_files/execs/metrosim
    # ./metrosim_files/arg_files/simulation_x_run_y.txt
    # && python3 ./metro_app/build_results.py y
    #
    # The python executable is the same as the one used by Django (i.e.
    # sys.executable).
    command = (
        '{executable} {first_script} {run_id} && '
        '{metrosim} {argfile} && '
        '{executable} {second_script} {run_id}'
    )
    command = command.format(
        executable=sys.executable, first_script=prepare_run_file,
        run_id=run.id, metrosim=metrosim_file, argfile=arg_file,
        second_script=build_results_file,
    )
    # Call the command in a shell and redirect stdout and stderr to the log
    # file.
    with open(log_file, 'w') as f:
        if background:
            subprocess.Popen(command, shell=True, stdout=f, stderr=f)

        else:
            subprocess.call(command, shell=True, stdout=f, stderr=f)


#Implemented a run_batch to run the external script.
def run_batch(batch):

    if batch.status == "Preparing":
        batch.status = "Running"

    batch_run_file = settings.BASE_DIR + '/metro_app/batch_run.py'
    log_file = (

        '{0}/website_files/script_logs/batch_{1}.txt'.format(
            settings.BASE_DIR, batch.id
        )
    )

    command = (
            '{executable} {first_script} {batch_id}'
            )

    command = command.format(

            executable=sys.executable, first_script=batch_run_file,
            batch_id=batch.id,
            )
    # Call the command in a shell and redirect stdout and stderr to the log
    # file.
    with open(log_file, "w") as f:
        subprocess.Popen(command, shell=True, stderr=f, stdout=f)


def get_export_directory():
    """Function to create a new directory used to export files."""
    # To avoid conflict if two users export a file at the same time, we put
    # the export file in a directory with a random name.
    while True:
        seed = np.random.randint(100)
        dir_name = \
            '{0}/website_files/exports/{1}'.format(settings.BASE_DIR, seed)
        try:
            os.makedirs(dir_name)
        except FileExistsError:
            pass
        else:
            return dir_name


def create_simulation(user, form):
    """Function to create a new simulation (with all its associated objects)
    from a form.

    Parameters
    ----------
    user: User object.
        Owner of the simulation.
    form: BaseSimulationForm or SimulationImportForm.
        Form containing basic data for the simulation (name, comment, etc.).
    """
    simulation = models.Simulation()
    simulation.user = user
    simulation.name = form.cleaned_data['name']
    simulation.comment = form.cleaned_data['comment']
    simulation.public = form.cleaned_data['public']
    simulation.environment = form.cleaned_data['environment']
    simulation.contact = form.cleaned_data['contact']
    # Create models associated with the new simulation.
    network = models.Network()
    network.name = simulation.name
    network.save()
    function_set = models.FunctionSet()
    function_set.name = simulation.name
    function_set.save()
    # Add defaults functions.
    function = models.Function(
        name='Free flow', user_id=1, expression='3600*(length/speed)')
    function.save()
    function.vdf_id = function.id
    function.save()
    function.functionset.add(function_set)
    function = models.Function(
        name='Bottleneck function', user_id=2,
        expression=(
            '3600*((dynVol<=(lanes*capacity*length/speed))*(length/speed)+'
            '(dynVol>(lanes*capacity*length/speed))*(dynVol/(capacity*lanes)))'
        ),
    )
    function.save()
    function.vdf_id = function.id
    function.save()
    function.functionset.add(function_set)
    pttimes = models.Matrices()
    pttimes.save()
    supply = models.Supply()
    supply.name = simulation.name
    supply.network = network
    supply.functionset = function_set
    supply.pttimes = pttimes
    supply.save()
    demand = models.Demand()
    demand.name = simulation.name
    demand.save()
    scenario = models.Scenario()
    scenario.name = simulation.name
    scenario.supply = supply
    scenario.demand = demand
    scenario.save()
    simulation.scenario = scenario
    # Save the simulation and return it.
    simulation.save()
    return simulation


#Method to Import a simulation as a zip_file(Calling this method in views.py)
def simulation_import(simulation, file):

    file = zipfile.ZipFile(file)
    namelist = file.namelist()

    for filename in namelist:
        if re.search('/zones.[tc]sv$', filename):
            object_import_function(
                file.open(filename), simulation, 'centroid')
            break

    for filename in namelist:
        if re.search('/intersections.[tc]sv$', filename):
            object_import_function(
                file.open(filename), simulation, 'crossing')
            break

    for filename in namelist:
        if re.search('/links.[tc]sv$', filename):
            object_import_function(
                file.open(filename), simulation, 'link')
            break

    for filename in namelist:
        if re.search('/congestion_functions.[tc]sv$', filename):
            object_import_function(
                file.open(filename), simulation, 'function')
            break

    for filename in namelist:
        if re.search('/public_transit.[tc]sv$', filename):
            public_transit_import_function(
                file.open(filename), simulation)
            break

    for filename in namelist:
        if re.search('/traveler_types.[tc]sv$', filename):
            usertype_import_function(
                file.open(filename), simulation)
            break

    demandsegments = get_query('demandsegment', simulation)
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
            matrix_import_function(
                file.open(filename), simulation, demandsegment)

    for filename in namelist:
        if re.search('/pricings.[tc]sv$', filename):
            pricing_import_function(
                file.open(filename), simulation)
            break


    return file



def traveler_zip_file(simulation, file):

    file = zipfile.ZipFile(file)
    namelist = file.namelist()

    for filename in namelist:
        if re.search('/traveler_types.[tc]sv$', filename):
            usertype_import_function(
                file.open(filename), simulation)
            break

    demandsegments = get_query('demandsegment', simulation)
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
            matrix_import_function(
                file.open(filename), simulation, demandsegment)

    return file

def object_import_function(encoded_file, simulation, object_name):
    """Function to import a file representing the input of a simulation.

    Parameters
    ----------
    encoded_file: File object.
        Input file, as given by request.FILES.
    simulation: Simulation object.
        Simulation to modify.
    object_name: String.
        Name of the input to modify: 'centroid', 'crossing', 'link' or
        'function'.

    This function could be much more simple but I tried to use as little as
    possible Django ORM (the querysets) to speed up the view.
    Basically, this view looks at each row in the imported file to find if an
    instance already exists for the row (user_id already used) or if a new
    instance needs to be created. If the instance already exists, the view
    compares the values in the file with the values in the database to know if
    the instance needs to be updated.
    Python built-in set are used to perform comparison of arrays quickly.
    """
    # Convert imported file to a csv DictReader.
    tsv_file = StringIO(encoded_file.read().decode())
    if encoded_file.name.split(".")[-1] == 'tsv':
        df = pd.read_csv(tsv_file, delimiter='\t')
    else:
        df = pd.read_csv(tsv_file, delimiter=',')
    # Do not do anything if the file is empty.
    num_lines = len(df)
    if num_lines == 0:
        return
    if object_name == 'function':
        parent = simulation.scenario.supply.functionset
    else:
        parent = simulation.scenario.supply.network
    query = get_query(object_name, simulation)
    user_id_set = set(query.values_list('user_id', flat=True))
    if object_name == 'link':
        # To import links, we retrieve the ids and user ids of all
        # centroids, crossings and functions in DataFrames.
        cols = ['user_id', 'id']
        centroids = get_query('centroid', simulation)
        centroid_df = pd.DataFrame(list(centroids.values_list(*cols)),
                                   columns=cols)
        crossings = get_query('crossing', simulation)
        crossing_df = pd.DataFrame(list(crossings.values_list(*cols)),
                                   columns=cols)
        node_df = pd.concat([centroid_df, crossing_df])
        functions = get_query('function', simulation)
        function_df = pd.DataFrame({
            'user_id': list(functions.values_list('user_id', flat=True)),
            'id': list(functions.values_list('id', flat=True)),
            'instance': list(functions),
        })
    # Name column is optionnal.
    # Create the column if it does not exist.
    if 'name' in df.columns:
        df['name'] = df['name'].astype(str)
    else:
        df['name'] = ''
    if object_name in ('centroid', 'crossing'):
        if object_name == 'centroid':
            # Do not import centroid with same id as a crossing.
            crossings = get_query('crossing', simulation)
            imported_ids = crossings.values_list('user_id', flat=True)
        else:
            # Do not import crossing with same id as a centroid.
            centroids = get_query('centroid', simulation)
            imported_ids = set(centroids.values_list('user_id', flat=True))
        df = df[['id', 'name', 'x', 'y']]
        df = df.loc[~df['id'].isin(imported_ids)]
    elif object_name == 'function':
        df = df[['id', 'name', 'expression']]
    elif object_name == 'link':
        # We need to add useful columns to the DataFrame.
        # Add column id_origin with the id of the origin node.
        df = df.merge(node_df, left_on='origin', right_on='user_id',
                      suffixes=('', '_origin'))
        # Add column id_destination with the id of the destination
        # node.
        df = df.merge(node_df, left_on='destination',
                      right_on='user_id',
                      suffixes=('', '_destination'))
        # Add column instance_function with the function object of the
        # given user_id.
        df = df.merge(function_df, left_on='function',
                      right_on='user_id', suffixes=('', '_function'))
        df = df[['id', 'name', 'id_origin', 'id_destination',
                 'id_function', 'instance', 'length', 'lanes', 'speed',
                 'capacity']]
    # Remove duplicated ids.
    df = df.drop_duplicates(subset='id', keep='last')
    # Check if user_id already exists.
    df['new'] = ~(df['id'].isin(user_id_set))
    if not df['new'].all():
        # Some existing objects needs to be updated.
        if object_name == 'link':
            new_values = set(
                map(tuple, df.loc[~df['new']].drop(
                    columns=['new', 'instance']
                ).values)
            )
        else:
            new_values = set(
                map(tuple, df.loc[~df['new']].drop(columns='new').values)
            )
        if object_name in ('centroid', 'crossing'):
            old_values = set(
                query.values_list('user_id', 'name', 'x', 'y')
            )
        elif object_name == 'function':
            old_values = set(
                query.values_list('user_id', 'name', 'expression')
            )
        elif object_name == 'link':
            old_values = set(
                query.values_list('user_id', 'name', 'origin',
                                  'destination', 'vdf_id', 'length',
                                  'lanes', 'speed', 'capacity')
            )
        # Find the instances that really need to be updated (i.e. the
        # values have changed).
        new_values = new_values.difference(old_values)
        if object_name in ('centroid', 'crossing', 'function'):
            # Update the objects (it would be faster to delete and
            # re-create them but this would require to also change the
            # foreign keys of the links).
            for values in new_values:
                # Index 0 of values is the id column i.e. the user_id.
                instance = query.filter(user_id=values[0])
                if object_name in ('centroid', 'crossing'):
                    instance.update(
                        name=values[1], x=values[2], y=values[3]
                    )
                else:  # Function
                    instance.update(name=values[1], expression=values[2])
        elif object_name == 'link':
            # Delete the updated links.
            user_ids = [values[0] for values in new_values]
            old_links = query.filter(user_id__in=user_ids)
            old_links.delete()
            # Re-create the updated links with the new links.
            df.loc[df['id'].isin(user_ids), 'new'] = True
    if df['new'].any():
        # Only keep the new objects.
        df = df.loc[df['new']]
        # Create the new objects in bulk.
        # The chunk size is limited by the MySQL engine (timeout if it is
        # too big).
        chunk_size = 10000
        new_objects = list()
        if object_name == 'centroid':
            for key, row in df.iterrows():
                new_objects.append(
                    models.Centroid(
                        user_id=row['id'], name=row['name'],
                        x=row['x'], y=row['y'],
                    )
                )
        elif object_name == 'crossing':
            for key, row in df.iterrows():
                new_objects.append(
                    models.Crossing(
                        user_id=row['id'], name=row['name'],
                        x=row['x'], y=row['y'],
                    )
                )
        elif object_name == 'function':
            for key, row in df.iterrows():
                new_objects.append(
                    models.Function(
                        user_id=row['id'], name=row['name'],
                        expression=row['expression'],
                    )
                )
        elif object_name == 'link':
            for key, row in df.iterrows():
                new_objects.append(
                    models.Link(
                        user_id=row['id'], name=row['name'],
                        origin=row['id_origin'],
                        destination=row['id_destination'], vdf=row['instance'],
                        length=row['length'], lanes=row['lanes'],
                        speed=row['speed'], capacity=row['capacity'],
                    )
                )
        chunks = [new_objects[x:x + chunk_size]
                  for x in range(0, len(new_objects), chunk_size)]
        for chunk in chunks:
            # Create the new instances.
            query.model.objects.bulk_create(chunk, chunk_size)
        # Retrieve new ids.
        last_id = query.model.objects.last().id
        new_ids = np.arange(last_id - len(new_objects) + 1, last_id + 1)
        # Add the many-to-many relation to Network or FunctionSet.
        relations = list()
        if object_name == 'function':
            for new_id in new_ids:
                relations.append(
                    query.model.functionset.through(
                        functionset_id=parent.id, function_id=new_id
                    )
                )
            query.model.functionset.through.objects.bulk_create(
                relations, batch_size=chunk_size
            )
        else:
            # Pass arguments as dict to avoid more if conditions.
            object_id = '{}_id'.format(object_name)
            for new_id in new_ids:
                relations.append(
                    query.model.network.through(
                        **{'network_id': parent.id, object_id: new_id}
                    )
                )
            query.model.network.through.objects.bulk_create(
                relations, batch_size=chunk_size
            )
    simulation.has_changed = True
    simulation.save()


def matrix_import_function(encoded_file, simulation, demandsegment):
    """Function to import a file representing the OD matrix of a usertype.

    Parameters
    ----------
    encoded_file: File object.
        Input file, as given by request.FILES.
    simulation: Simulation object.
        Simulation to modify.
    demandsegment: DemandSegment object.
        Demand segment for which the OD matrix must be modified.

    This function could be much more simple but I tried to use as little as
    possible Django ORM (the querysets). When written with standard Django
    querysets and save methods, it took hours to import a large OD matrix.
    Basicaly, this view looks at each row in the imported file to know if the
    OD pair of the row already exists or needs to be created. If it already
    exists, the view looks at the population value to know if the value needs
    to be updated. To update values, we simply delete the previous entries in
    the database and insert the new ones.
    """
    tsv_file = StringIO(encoded_file.read().decode())
    # Do not do anything if the file is empty.
    num_lines = sum(1 for row in tsv_file)
    if num_lines <= 1:
        return
    tsv_file.seek(0)
    # Convert the imported file to a csv DictReader.
    if encoded_file.name.split(".")[-1] == 'tsv':
        reader = csv.DictReader(tsv_file, delimiter='\t')
    else:
        reader = csv.DictReader(tsv_file, delimiter=',')
    # Create a set with all existing OD pairs in the OD matrix.
    matrix = demandsegment.matrix
    pairs = models.Matrix.objects.filter(matrices=matrix)
    existing_pairs = set(pairs.values_list('p_id', 'q_id'))
    # Create a dictionary to map the centroid user ids with the centroid
    # objects.
    centroids = get_query('centroid', simulation)
    centroid_mapping = dict()
    centroid_id_mapping = dict()
    for centroid in centroids:
        centroid_mapping[centroid.user_id] = centroid
        centroid_id_mapping[centroid.user_id] = centroid.id
    # For each imported OD pair, if the pair already exists in t
    # For each imported OD pair, if the pair already exists in the OD Matrix,
    # it is stored to be updated, else it is stored to be created.
    to_be_updated = set()
    to_be_created = list()
    for row in reader:
        try:
            pair = (
                centroid_id_mapping[int(row['origin'])],
                centroid_id_mapping[int(row['destination'])]
            )
        except KeyError:
            # Unable to find centroid origin or destination.
            continue
        if pair in existing_pairs:
            to_be_updated.add((*pair, float(row['population'])))
        elif float(row['population']) > 0:
            to_be_created.append(
                models.Matrix(
                    p=centroid_mapping[int(row['origin'])],
                    q=centroid_mapping[int(row['destination'])],
                    r=float(row['population']), matrices=matrix,
                )
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
            chunks = [to_be_updated_ids[x:x + chunk_size]
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
            models.Matrix(
                p=centroid_id_mapping[pair[0]], q=centroid_id_mapping[pair[1]],
                r=pair[2], matrices=matrix,
            )
            for pair in to_be_updated
        ]
    # Create the new OD pairs in bulk.
    # The chunk size is limited by the MySQL engine (timeout if it is too big).
    chunk_size = 20000
    chunks = [to_be_created[x:x + chunk_size]
              for x in range(0, len(to_be_created), chunk_size)]
    for chunk in chunks:
        models.Matrix.objects.bulk_create(chunk, chunk_size)
    # Update total.
    pairs = pairs.all()  # Update queryset from database.
    if pairs.exists():
        matrix.total = int(
            demandsegment.scale * pairs.aggregate(Sum('r'))['r__sum']
        )
    else:
        matrix.total = 0
    matrix.save()
    simulation.has_changed = True
    simulation.save()


def pricing_import_function(encoded_file, simulation):
    """Function to import a file as tolls in the database.

    Parameters
    ----------
    encoded_file: File object.
        Input file, as given by request.FILES.
    simulation: Simulation object.
        Simulation to modify.
    """
    tsv_file = StringIO(encoded_file.read().decode())
    # Do not do anything if the file is empty.
    num_lines = sum(1 for row in tsv_file)
    if num_lines <= 1:
        return
    tsv_file.seek(0)
    # Convert the imported file to a csv DictReader.
    if encoded_file.name.split(".")[-1] == 'tsv':
        reader = csv.DictReader(tsv_file, delimiter='\t')
    else:
        reader = csv.DictReader(tsv_file, delimiter=',')
    # Get all pricing policies for this usertype.
    policies = get_query('policy', simulation)
    tolls = policies.filter(type='PRICING')
    # Get all links of the network.
    links = get_query('link', simulation)
    # Get all LinkSelection of the network.
    locations = models.LinkSelection.objects.filter(
        network=simulation.scenario.supply.network
    )
    # Get all usertypes.
    usertypes = get_query('usertype', simulation)
    # Get an empty Vector or create one if there is none.
    if models.Vector.objects.filter(data='').exists():
        empty_vector = models.Vector.objects.filter(data='')[0]
    else:
        empty_vector = models.Vector(data='')
        empty_vector.save()
    if 'traveler_type' in reader.fieldnames:
        has_type = True
    else:
        has_type = False
    if 'times' in reader.fieldnames:
        has_times = True
    else:
        has_times = False
    # For each imported link, if a Policy exists for the link, baseValue is
    # updated, else a new Policy is created.
    for row in reader:
        # Get link of current row.
        link = links.get(user_id=row['link'])
        # Get or create a LinkSelection associated with the link.
        if locations.filter(link=link).exists():
            # Take first matching LinkSelection.
            location = locations.filter(link=link)[0]
        else:
            # Create a LinkSelection for the current link.
            # Name and user_id of the Link Selection are set to the name
            # and user_id of the link.
            location = models.LinkSelection(
                network=simulation.scenario.supply.network,
                name=link.name,
                user_id=link.user_id,
            )
            location.save()
            location.link.add(link)
        # Get or create a pricing Policy with the corret LinkSelection
        # object.
        try:
            toll = tolls.get(location=location)
        except models.Policy.DoesNotExist:
            # Create a new toll with default values.
            toll = models.Policy(
                location=location, type='PRICING', usertype=None,
                valueVector=empty_vector, timeVector=empty_vector,
            )
            toll.save()
            toll.scenario.add(simulation.scenario)
        # Update affected traveler type.
        toll.usertype = None
        if has_type:
            try:
                toll.usertype = usertypes.get(user_id=row['traveler_type'])
            except (models.UserType.DoesNotExist, ValueError):
                # Usertype has not been found, set the toll as a global policy.
                pass
        # Update values.
        values = row['values'].split(',')
        # First value is baseValue.
        toll.baseValue = float(values[0])
        if len(values) > 1:
            # Remaining values are stored in valueVector (as a string of
            # comma separated values).
            values = [str(float(x)) for x in values]
            v = models.Vector(data=','.join(values[1:]))
            v.save()
            toll.valueVector = v
        else:
            toll.valueVector = empty_vector
        # Update times.
        toll.timeVector = empty_vector
        if has_times:
            times = row['times'].split(',')
            if times[0] != ' ' and times[0]:
                # There is at least one value, store it in timeVector.
                times = [str(int(x)) for x in times]
                v = models.Vector(data=','.join(times))
                v.save()
                toll.timeVector = v
        toll.save()


def public_transit_import_function(encoded_file, simulation):
    """Function to import a file as a public transit matrix in the database.

    Parameters
    ----------
    encoded_file: File object.
        Input file, as given by request.FILES.
    simulation: Simulation object.
        Simulation to modify.
    """
    tsv_file = StringIO(encoded_file.read().decode())
    # Do not do anything if the file is empty.
    num_lines = sum(1 for row in tsv_file)
    if num_lines <= 1:
        return
    tsv_file.seek(0)
    # Convert the imported file to a csv DictReader.
    if encoded_file.name.split(".")[-1] == 'tsv':
        reader = csv.DictReader(tsv_file, delimiter='\t')
    else:
        reader = csv.DictReader(tsv_file, delimiter=',')
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
                models.Matrix(
                    p=centroid_mapping[int(row['origin'])],
                    q=centroid_mapping[int(row['destination'])],
                    r=float(row['travel time']), matrices=matrix,
                )
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
            chunks = [to_be_updated_ids[x:x + chunk_size]
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
            models.Matrix(
                p=centroid_id_mapping[pair[0]], q=centroid_id_mapping[pair[1]],
                r=pair[2], matrices=matrix,
            )
            for pair in to_be_updated
        ]
    # Create the new OD pairs in bulk.
    # The chunk size is limited by the MySQL engine (timeout if it is too big).
    chunk_size = 20000
    chunks = [to_be_created[x:x + chunk_size]
              for x in range(0, len(to_be_created), chunk_size)]
    for chunk in chunks:
        models.Matrix.objects.bulk_create(chunk, chunk_size)


def usertype_import_function(encoded_file, simulation):
    """Function to import a file as a new usertype in the database.

    Parameters
    ----------
    encoded_file: File object.
        Input file, as given by request.FILES.
    simulation: Simulation object.
        Simulation to modify.
    """
    tsv_file = StringIO(encoded_file.read().decode())
    # Do not do anything if the file is empty.
    num_lines = sum(1 for row in tsv_file)
    if num_lines <= 1:
        return
    tsv_file.seek(0)
    # Convert the imported file to a csv DictReader.
    if encoded_file.name.split(".")[-1] == 'tsv':
        reader = csv.DictReader(tsv_file, delimiter='\t')
    else:
        reader = csv.DictReader(tsv_file, delimiter=',')
    # Get an empty Vector or create one if there is none.
    if models.Vector.objects.filter(data='').exists():
        empty_vector = models.Vector.objects.filter(data='')[0]
    else:
        empty_vector = models.Vector(data='')
        empty_vector.save()

    for row in reader:

        user_id = row['id']
        name = row['name']
        comment = row['comment']

        mean = row['alphaTI_mean']
        std = row['alphaTI_std']
        dtype = row['alphaTI_type']
        alphaTI = models.Distribution(mean=mean, std=std, type=dtype)
        alphaTI.save()

        mean = row['alphaTP_mean']
        std = row['alphaTP_std']
        dtype = row['alphaTP_type']
        alphaTP = models.Distribution(mean=mean, std=std, type=dtype)
        alphaTP.save()

        mean = row['beta_mean']
        std = row['beta_std']
        dtype = row['beta_type']
        beta = models.Distribution(mean=mean, std=std, type=dtype)
        beta.save()

        mean = row['delta_mean']
        std = row['delta_std']
        dtype = row['delta_type']
        delta = models.Distribution(mean=mean, std=std, type=dtype)
        delta.save()

        mean = row['departureMu_mean']
        std = row['departureMu_std']
        dtype = row['departureMu_type']
        departureMu = models.Distribution(mean=mean, std=std, type=dtype)
        departureMu.save()

        mean = row['gamma_mean']
        std = row['gamma_std']
        dtype = row['gamma_type']
        gamma = models.Distribution(mean=mean, std=std, type=dtype)
        gamma.save()

        mean = row['modeMu_mean']
        std = row['modeMu_std']
        dtype = row['modeMu_type']
        modeMu = models.Distribution(mean=mean, std=std, type=dtype)
        modeMu.save()

        mean = row['penaltyTP_mean']
        std = row['penaltyTP_std']
        dtype = row['penaltyTP_type']
        penaltyTP = models.Distribution(mean=mean, std=std, type=dtype)
        penaltyTP.save()

        mean = row['routeMu_mean']
        std = row['routeMu_std']
        dtype = row['routeMu_type']
        routeMu = models.Distribution(mean=mean, std=std, type=dtype)
        routeMu.save()

        mean = row['tstar_mean']
        std = row['tstar_std']
        dtype = row['tstar_type']
        tstar = models.Distribution(mean=mean, std=std, type=dtype)
        tstar.save()

        typeOfRouteChoice = row['typeOfRouteChoice']
        typeOfDepartureMu = row['typeOfDepartureMu']
        typeOfRouteMu = row['typeOfRouteMu']
        typeOfModeMu = row['typeOfModeMu']
        localATIS = row['localATIS']
        modeChoice = row['modeChoice']
        modeShortRun = row['modeShortRun']
        commuteType = row['commuteType']

        usertypes = get_query('usertype', simulation)
        # If there is already an usertype with the same user_id, we delete it
        # and replace it with the new usertype.
        try:
            existing_usertype = usertypes.get(user_id=user_id)
            demandsegment = existing_usertype.demandsegment_set.first()
        except models.UserType.DoesNotExist:
            demandsegment = None

        if not user_id:
            # Set the user_id of the new usertype to the next available id.
            if usertypes.exists():
                user_id = usertypes.last().user_id + 1
            else:
                user_id = 1

        usertype = models.UserType()
        usertype.user_id = user_id
        usertype.name = name
        usertype.comment = comment
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
        usertype.typeOfRouteChoice = typeOfRouteChoice
        usertype.typeOfDepartureMu = typeOfDepartureMu
        usertype.typeOfRouteMu = typeOfRouteMu
        usertype.typeOfModeMu = typeOfModeMu
        usertype.localATIS = localATIS
        usertype.modeChoice = modeChoice
        usertype.modeShortRun = modeShortRun
        usertype.commuteType = commuteType
        usertype.save()

        if demandsegment is None:
            # Create a new demand segment and OD matrix for the usertype.
            matrix = models.Matrices()
            matrix.save()
            demandsegment = models.DemandSegment()
            demandsegment.usertype = usertype
            demandsegment.matrix = matrix
            demandsegment.save()
            demandsegment.demand.add(simulation.scenario.demand)
        else:
            demandsegment.usertype = usertype
            demandsegment.save()
            # We also need to update the usertype of policies.
            policies = models.Policy.objects.filter(usertype=existing_usertype)
            policies.update(usertype=usertype)
            # We can now safely delete the old usertype.
            existing_usertype.delete()


######################
#  Export functions  #
######################


def matrix_export_function(simulation, demandsegment, dir_name):
    """Function to save the OD matrix as a tsv file."""
    matrix = demandsegment.matrix
    matrix_couples = models.Matrix.objects.filter(matrices=matrix)
    if not matrix_couples.exists():
        return
    filename = os.path.join(
        dir_name,
        'matrix_{}.tsv'.format(demandsegment.usertype.user_id)
    )

    with codecs.open(filename, 'w', encoding='utf8') as f:
        writer = csv.writer(f, delimiter='\t')
        # Get a dictionary with all the values to export.
        values = matrix_couples.values_list('p__user_id', 'q__user_id', 'r')
        # Write a custom header.
        writer.writerow(['origin', 'destination', 'population'])
        writer.writerows(values)

    return filename


def pricing_export_function(simulation, dir_name):
    """Function to save the tolls of an user type as a tsv file."""
    # Get all tolls.
    policies = get_query('policy', simulation)
    tolls = policies.filter(type='PRICING')
    if not tolls.exists():
        return
    filename = os.path.join(dir_name, 'pricings.tsv')

    with codecs.open(filename, 'w', encoding='utf8') as f:
        writer = csv.writer(f, delimiter='\t')
        # Get a dictionary with all the values to export.
        values = list()
        for toll in tolls:
            if toll.usertype:
                usertype_id = toll.usertype.user_id
            else:
                usertype_id = ''
            values.append([toll.location.user_id, toll.get_value_vector(),
                           toll.get_time_vector(), usertype_id])
        # Write a custom header.
        writer.writerow(['link', 'values', 'times', 'traveler_type'])
        writer.writerows(values)

    return filename


def public_transit_export_function(simulation, dir_name):
    """Function to save the public transit OD Matrix as a tsv file."""
    matrix_couples = get_query('public_transit', simulation)
    if not matrix_couples.exists():
        return
    filename = os.path.join(dir_name, 'public_transit.tsv')

    with codecs.open(filename, 'w', encoding='utf8') as f:
        writer = csv.writer(f, delimiter='\t')
        # Get a dictionary with all the values to export.
        values = matrix_couples.values_list('p__user_id', 'q__user_id', 'r')
        # Write a custom header.
        writer.writerow(['origin', 'destination', 'travel time'])
        writer.writerows(values)

    return filename


def object_export_function(simulation, object_name, dir_name):
    """Function to save all instances of a network object as a tsv file."""
    query = get_query(object_name, simulation)
    if not query.exists():
        return
    name = metro_to_user(object_name).replace(' ', '_')
    filename = os.path.join(dir_name, '{}s.tsv'.format(name))

    with codecs.open(filename, 'w', encoding='utf8') as f:
        writer = csv.writer(f, delimiter='\t')
        if object_name in ('centroid', 'crossing'):
            writer.writerow(['id', 'name', 'x', 'y', 'db_id'])
            values = query.values_list('user_id', 'name', 'x', 'y', 'id')
        elif object_name == 'function':
            writer.writerow(['id', 'name', 'expression'])
            values = query.values_list('user_id', 'name', 'expression')
        elif object_name == 'link':
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
            if values:
                values = np.hstack([values, origins, destinations])
        writer.writerows(values)

    return filename


def usertype_export_function(simulation, demandsegment=None, dir_name=''):
    """Function to save the parameters of the usertypes as a tsv file."""
    filename = os.path.join(dir_name, 'traveler_types.tsv')
    # Get a dictionary with all the values to export.
    if demandsegment is None:
        # Export all usertypes of the simulation.
        usertypes = get_query('usertype', simulation)
    else:
        # Export only the usertype for the given demandsegment.
        usertype = demandsegment.usertype
        usertypes = models.UserType.objects.filter(pk=usertype.id)
    if not usertypes.exists():
        return

    with codecs.open(filename, 'w', encoding='utf8') as f:
        writer = csv.writer(f, delimiter='\t')

        values = usertypes.values_list(
            'user_id', 'name', 'comment', 'alphaTI__mean', 'alphaTI__std',
            'alphaTI__type', 'alphaTP__mean', 'alphaTP__std', 'alphaTP__type',
            'beta__mean', 'beta__std', 'beta__type', 'delta__mean',
            'delta__std', 'delta__type', 'departureMu__mean',
            'departureMu__std', 'departureMu__type', 'gamma__mean',
            'gamma__std', 'gamma__type', 'modeMu__mean', 'modeMu__std',
            'modeMu__type', 'penaltyTP__mean', 'penaltyTP__std',
            'penaltyTP__type', 'routeMu__mean', 'routeMu__std',
            'routeMu__type', 'tstar__mean', 'tstar__std', 'tstar__type',
            'typeOfRouteChoice', 'typeOfDepartureMu', 'typeOfRouteMu',
            'typeOfModeMu', 'localATIS', 'modeChoice', 'modeShortRun',
            'commuteType'
        )

        # Write a custom header.
        writer.writerow([
            'id', 'name', 'comment', 'alphaTI_mean', 'alphaTI_std',
            'alphaTI_type', 'alphaTP_mean', 'alphaTP_std', 'alphaTP_type',
            'beta_mean', 'beta_std', 'beta_type', 'delta_mean', 'delta_std',
            'delta_type', 'departureMu_mean', 'departureMu_std',
            'departureMu_type', 'gamma_mean', 'gamma_std', 'gamma_type',
            'modeMu_mean', 'modeMu_std', 'modeMu_type', 'penaltyTP_mean',
            'penaltyTP_std', 'penaltyTP_type', 'routeMu_mean', 'routeMu_std',
            'routeMu_type', 'tstar_mean', 'tstar_std', 'tstar_type',
            'typeOfRouteChoice', 'typeOfDepartureMu', 'typeOfRouteMu',
            'typeOfModeMu', 'localATIS', 'modeChoice', 'modeShortRun',
            'commuteType'
        ])

        writer.writerows(values)
    return filename






