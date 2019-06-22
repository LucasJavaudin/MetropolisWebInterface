#!/usr/bin/env python3
"""This file is automatically executed after a metropolis run has ended.

The disaggregated output of Metrosim is read and converted to json suitable for
display on the website.
The status of the SimulationRun is modified to 'Over' and an e-mail is sent to
the user.
This file must be run with the run id as an argument.
This file must be in the directory metro_app.
Author: Lucas Javaudin
E-mail: lucas.javaudin@ens-paris-saclay.fr
"""

print('Starting script...')

# Execute the script with the virtualenv.
try:
    activate_this_file = '/home/metropolis/python3/bin/activate_this.py'
    with open(activate_this_file) as f:
        exec(f.read(), {'__file__': activate_this_file})
except FileNotFoundError:
    print('Running script without a virtualenv.')
    pass

import os
import os.path
import sys
import csv
import json
import codecs

# Set matplotlib config directory.
mplconfigdir = '/home/metropolis/matplotlib'
if os.path.isdir(mplconfigdir):
    os.environ['MPLCONFIGDIR'] = mplconfigdir

import django
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import connection

from matplotlib.colors import LinearSegmentedColormap
import numpy as np

# Load the django website.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "metropolis_web_interface.settings")
django.setup()

from metro_app.models import *
from metro_app.views import LINK_THRESHOLD, NETWORK_THRESHOLD
from metro_app.functions import *


def import_output(run):
    """Import the results of the SimulationRun.

    Return a dictionary with the ids of the links and a numpy array with the
    results for each type.
    """
    simulation = run.simulation
    output_dir = settings.BASE_DIR + '/metrosim_files/output/'
    output_file = output_dir + 'metrosim_net_arcs_{0}_{1}_{2!s}.txt'
    db_name = settings.DATABASES['default']['NAME']
    output = dict()

    # Store the ids of the links in a list.
    output['link_ids'] = []
    current_output_file = output_file.format('phi_in_H', db_name,
                                             simulation.id)
    with open(current_output_file, newline='') as tsv_file:
        reader = csv.reader(tsv_file, delimiter='\t')
        for row in reader:
            output['link_ids'].append(row[0])

    if len(output['link_ids']) >= LINK_THRESHOLD:
        # Large network, only store one type of results (phi_in_H).
        output_types = ['phi_in_H', 'ttime_H']
    else:
        # Small network, we can store everything.
        output_types = ['phi_in_H', 'phi_in_S', 'phi_out_H', 'phi_out_S',
                        'ttime_H', 'ttime_S']

    for output_type in output_types:
        # Build a list for each output type.
        output[output_type] = []
        current_output_file = output_file.format(output_type, db_name,
                                                 simulation.id)
        with open(current_output_file, newline='') as tsv_file:
            reader = csv.reader(tsv_file, delimiter='\t')
            for row in reader:
                # Create a list to store the output of this link.
                link_output = []
                # Store link id (only once).
                for period in range(1, len(row) - 1):  # Last column is empty.
                    link_output.append(row[period])
                output[output_type].append(link_output)
        # Convert the list to a numpy array.
        # There is a numpy array for each output type.
        # The numpy array has one row for each link and one column for each
        # period.
        output[output_type] = np.array(output[output_type], dtype=np.int16)
    return output


def export_link_results(output, export_file):
    # Create a dictionary to map the link ids with the link user ids.
    link_mapping = dict()
    links = get_query('link', SIMULATION.id)
    for link in links:
        link_mapping[link.id] = link.user_id
    # Check size of network.
    large_network = len(output['link_ids']) >= LINK_THRESHOLD
    # Write a csv.
    with codecs.open(export_file, 'w', encoding='utf8') as f:
        writer = csv.writer(f, delimiter='\t')
        # Writer a custom header.
        if large_network:
            labels = ['in-flow_H', 'ttime_H']
        else:
            labels = ['in-flow_H', 'in-flow_S', 'out-flow_H', 'out-flow_S',
                      'ttime_H', 'ttime_S']
        nb_periods = len(output['phi_in_H'][0])
        headers = ['{}_{}'.format(l, i + 1)
                   for l in labels
                   for i in range(nb_periods)]
        headers = ['link'] + headers
        writer.writerow(headers)
        # Write rows.
        if large_network:
            # Large network, only store one type of results (phi_in_H).
            output_types = ['phi_in_H', 'ttime_H']
        else:
            # Small network, we can store everything.
            output_types = ['phi_in_H', 'phi_in_S', 'phi_out_H', 'phi_out_S',
                            'ttime_H', 'ttime_S']
        for i, link_id in enumerate(output['link_ids']):
            link_id = int(link_id)
            link_user_id = link_mapping[link_id]
            row = [link_user_id]
            for output_type in output_types:
                values = output[output_type][i]
                row += list(values)
            writer.writerow(row)


def build_results(output):
    """Convert the results to color values.

    Return a dictionary with the same structure as the network output with the
    results for each links, a colorscale and stats for each output type.
    """
    link_ids = output['link_ids']
    results = dict()
    results['stats'] = dict()

    # Create a colorscale.
    cmap = congestion_colormap()
    transparency = .8
    size = 500
    colorscale_values = np.arange(0, size, 1)
    colorscale = [cmap(val / (size - 1)) for val in colorscale_values]
    colorscale = [
        'rgba({0}, {1}, {2}, {3})'.format(color[0] * 255, color[1] * 255,
                                          color[2] * 255, transparency)
        for color in colorscale]
    results['colorscale'] = colorscale

    if len(link_ids) > NETWORK_THRESHOLD:
        # Large network.
        output_types = ['phi_in_H', 'ttime_H']
    else:
        # Small network.
        output_types = ['phi_in_H', 'phi_in_S', 'phi_out_H', 'phi_out_S',
                        'ttime_H', 'ttime_S']

    for output_type in output_types:
        type_results = output[output_type]
        periods = np.arange(0, np.shape(type_results)[1])

        # Add aggregated results for the output type.
        results['stats'][output_type] = dict()
        type_max = np.max(type_results)
        results['stats'][output_type]['max'] = float(type_max)
        type_min = np.min(type_results)
        results['stats'][output_type]['min'] = float(type_min)
        type_average = np.mean(type_results)
        results['stats'][output_type]['average'] = float(type_average)

        results[output_type] = dict()
        results[output_type]['values'] = dict()
        results[output_type]['colors'] = dict()
        for i, link_id in enumerate(link_ids):
            link_id = str(link_id)
            results[output_type]['values'][link_id] = dict()
            results[output_type]['colors'][link_id] = dict()
            for period in periods:
                period = int(period)
                # Add the values.
                results[output_type]['values'][link_id][str(period)] = \
                    int(type_results[i, period])
                # Add the colors.
                results[output_type]['colors'][link_id][str(period)] = \
                    value_to_color(type_results[i, period], cmap, 0, type_max)

    return results


def export_network_results(run, results):
    """Sore the built results to a json file."""
    simulation = run.simulation
    output_file = (
        '{0}/website_files/network_output/results_{1}_{2}.json'
            .format(settings.BASE_DIR, simulation.id, run.id)
    )
    with open(output_file, 'w') as f:
        json.dump(results, f)


def clean_files(run):
    """Remove some files which are used during the run and are no longer
    necessary."""
    simulation = run.simulation
    metrosim_dir = settings.BASE_DIR + '/metrosim_files/'

    # try:
    # log_file = '{0}logs/run_{1!s}.txt'.format(metrosim_dir, run.id)
    # os.remove(log_file)
    # except FileNotFoundError:
    # pass

    try:
        arg_file = ('{0}argfiles/simulation_{1!s}_run_{2!s}.txt'
                    .format(metrosim_dir, simulation.id, run.id))
        os.remove(arg_file)
    except FileNotFoundError:
        pass

    output_types = ['phi_in_H', 'phi_in_S', 'phi_out_H', 'phi_out_S',
                    'ttime_H', 'ttime_S']
    db_name = settings.DATABASES['default']['NAME']
    result_file = metrosim_dir + 'output/metrosim_net_arcs_{0}_{1}_{2!s}.txt'
    for output_type in output_types:
        try:
            output_file = result_file.format(output_type, db_name,
                                             simulation.id)
            os.remove(output_file)
        except FileNotFoundError:
            pass


def end_run(run, failed=False):
    """Change the status of the SimulationRun and send an e-mail to the user.
    """
    # End the SimulationRun.
    run.end_time = timezone.now()
    run.time_taken = run.end_time - run.start_time
    if failed:
        run.status = 'Failed'
    else:
        run.status = 'Over'
    run.save()


def congestion_colormap():
    """Return a matplotlib colormap that looks good to visualize congestion."""
    cmap_name = 'congestion_colormap'
    colors = [
        (153 / 255, 255 / 255, 102 / 255),  # light green
        (255 / 255, 219 / 255, 77 / 255),  # yellowish
        (255 / 255, 0, 0),  # red
    ]
    cmap = LinearSegmentedColormap.from_list(cmap_name, colors)
    return cmap


def value_to_color(val, cmap, min_val, max_val):
    """Return the rgb color of a value using a color map."""
    # Express value in percentage of the interval [min_val, max_val].
    val = (val - min_val) / (max_val - min_val)
    # Find the color corresponding to the value. The result is in format
    # (1, 1, 1).
    color = cmap(val)
    # Convert the result to a format compatible with javascript:
    # 'rgb(255, 255, 255)'.
    color = 'rgb({0}, {1}, {2})'.format(int(color[0] * 255),
                                        int(color[1] * 255),
                                        int(color[2] * 255))
    return color


def clean_database(simulation):
    """Drop from the database the tables created for the run."""
    matrices = get_query('matrices', simulation)
    matrices_id = list(matrices.values_list('id', flat=True))
    matrices_id.append(simulation.scenario.supply.pttimes.id)
    with connection.cursor() as cursor:
        for matrice_id in matrices_id:
            cursor.execute(
                "DROP TABLE IF EXISTS Matrix_{id};"
                    .format(id=matrice_id)
            )


print('Reading the script argument')

# Read argument of the script call.
try:
    RUN_ID = int(sys.argv[1])
except IndexError:
    raise SystemExit('MetroArgError: This script must be executed with the id '
                     + 'of the SimulationRun has an argument.')

print('Finding SimulationRun')

# Get the SimulationRun object of the argument.
try:
    RUN = SimulationRun.objects.get(pk=RUN_ID)
except SimulationRun.DoesNotExist:
    raise SystemExit('MetroDoesNotExist: No SimulationRun object corresponding'
                     + ' to the given id.')

SIMULATION = RUN.simulation
# Change the status of the run.
RUN.status = 'Ending'
RUN.save()

try:
    print('Importing output...')
    OUTPUT = import_output(RUN)
    print('Writing link-specific results file...')
    EXPORT_FILE = (
        '{0}/website_files/network_output/link_results_{1}_{2}.txt'
            .format(settings.BASE_DIR, SIMULATION.id, RUN.id)
    )
    export_link_results(OUTPUT, EXPORT_FILE)
    print('Preparing the network view...')
    RESULTS = build_results(OUTPUT)
    print('Exporting results...')
    export_network_results(RUN, RESULTS)
    print('Cleaning files...')
    clean_files(RUN)
    print('Cleaning database...')
    clean_database(SIMULATION)
except (FileNotFoundError, json.decoder.JSONDecodeError, Exception) as e:
    # Catch any error (I explicitely write the two most common errors).
    print('Ending run with error(s)...')
    end_run(RUN, failed=True)
    raise e

print('Checking if network results are correctly stored...')
FILE = (
    '{0}/website_files/network_output/results_{1}_{2}.json'
        .format(settings.BASE_DIR, SIMULATION.id, RUN.id)
)
if os.path.isfile(FILE):
    RUN.network_output = True
if os.path.isfile(EXPORT_FILE):
    RUN.link_output = True

DB_NAME = settings.DATABASES['default']['NAME']

# Create a tsv file with a readable user-specific output.
print('Writing traveler-specific output...')
FILE = (
    '{0}/metrosim_files/output/metrosim_users_{1}_{2}.txt'
        .format(settings.BASE_DIR, DB_NAME, SIMULATION.id)
)
if os.path.isfile(FILE):
    try:
        EXPORT_FILE = (
            '{0}/website_files/network_output/user_results_{1}_{2}.txt'
                .format(settings.BASE_DIR, SIMULATION.id, RUN.id)
        )
        # Create a dictionary to map the centroid ids with the centroid user ids.
        centroid_mapping = dict()
        centroids = get_query('centroid', SIMULATION.id)
        for centroid in centroids:
            centroid_mapping[centroid.id] = centroid.user_id
        # Create a dictionary to map the demandsegment ids with the name of the
        # usertype.
        usertype_mapping = dict()
        demandsegments = DemandSegment.objects.filter(
            demand__scenario__simulation=SIMULATION
        )
        for demandsegment in demandsegments:
            if demandsegment.usertype.name:
                usertype_mapping[demandsegment.id] = demandsegment.usertype.name
            else:
                usertype_mapping[demandsegment.id] = demandsegment.usertype.id
        with codecs.open(FILE, 'r', encoding='utf8') as f:
            with codecs.open(EXPORT_FILE, 'w', encoding='utf8') as g:
                reader = csv.reader(f, delimiter='\t')
                writer = csv.writer(g, delimiter='\t')
                # Writer a custom header.
                writer.writerow(['origin', 'destination', 'travelerType',
                                 'driveCar', 'alphaTI', 'beta', 'gamma',
                                 'alphaPT',
                                 'ptPenalty', 'td', 'ta', 'ltstart', 'htstar',
                                 'fee', 'surplus'])
                for row in reader:
                    origin_id = centroid_mapping[int(row[0])]
                    destination_id = centroid_mapping[int(row[1])]
                    traveler_type = usertype_mapping[int(row[2])]
                    writer.writerow([origin_id, destination_id, traveler_type,
                                     row[3], row[4], row[5], row[6], row[7],
                                     row[8],
                                     row[9], row[10], row[11], row[12], row[13],
                                     row[14]])
    except Exception as e:
        print('Error while writing user-specific results file')
        print(e)

if os.path.isfile(EXPORT_FILE):
    RUN.user_output = True

RUN.save()

print('Ending run...')

end_run(RUN)

print('Done.')
