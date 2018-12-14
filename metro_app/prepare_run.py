"""This file is automatically executed before a metropolis run starts.

The current state of the simulation's network is stored in a json file.
The current parameters of the simulation are stored in a json file.
This file must be run with the run id as an argument.
This file must be in the directory metro_app.
Author: Lucas Javaudin
E-mail: lucas.javaudin@ens-paris-saclay.fr
"""
# Execute the script with the virtualenv.
try:
    activate_this_file = '/home/metropolis/python3/bin/activate_this.py'
    with open(activate_this_file) as f:
            exec(f.read(), {'__file__': activate_this_file})
except FileNotFoundError:
    print('Running script without a virtualenv.')
    pass

import os
import sys
import json
from shutil import copyfile

import django
from django.conf import settings
from django.db.models import Sum

# Load the django website.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "metropolis_web_interface.settings")
django.setup()

from metro_app.models import Simulation, SimulationRun, Link
from metro_app.functions import get_query
from metro_app.plots import network_output
from metro_app.views import NETWORK_THRESHOLD
TRAVELERS_THRESHOLD = 10000000 # 10 millions

print('Starting script...')

# Read argument of the script call.
try:
    run_id = int(sys.argv[1])
except IndexError:
    raise SystemExit('MetroArgError: This script must be executed with the id '
                     + 'of the SimulationRun has an argument.')

# Get the SimulationRun object of the argument.
try:
    run = SimulationRun.objects.get(pk=run_id)
except SimulationRun.DoesNotExist:
    raise SystemExit('MetroDoesNotExist: No SimulationRun object corresponding'
                     + ' to the given id.')

simulation = run.simulation

# Output user-specific results only if the population is small.
# I believe that Metropolis does not output the file correctly if the
# population is large.
matrices = get_query('matrices', simulation)
nb_travelers = matrices.aggregate(Sum('total'))['total__sum']
if nb_travelers > TRAVELERS_THRESHOLD:
    simulation.outputUsersTimes = 'false'
else:
    simulation.outputUsersTimes = 'true'
simulation.save()

# Use the existing network output file if it exists.
simulation_network = (
    '{0}/website_files/network_output/network_{1}.json'
    .format(settings.BASE_DIR, simulation.id)
)
if simulation.has_changed or not os.path.isfile(simulation_network):
    # Generate a new output file.
    print('Network file does not exist, generating a new one...')
    links = get_query('link', simulation)
    large_network = links.count() > NETWORK_THRESHOLD
    output = network_output(simulation, large_network)
    with open(simulation_network, 'w') as f:
        json.dump(output, f)
    # Do not generate a new output file the next time (unless the
    # simulation changes).
    simulation.has_changed = False
    simulation.save()
# The current network of the simulation is stored as the network of the
# run.
print('Copying the network json file...')
run_network = (
    '{0}/website_files/network_output/network_{1}_{2}.json'
    .format(settings.BASE_DIR, simulation.id, run.id)
)
copyfile(simulation_network, run_network)

# Store the current parameters of the simulation in a file.
print('Storing the parameters of the simulation...')
run_parameters = (
    '{0}/website_files/network_output/parameters_{1}_{2}.json'
    .format(settings.BASE_DIR, simulation.id, run.id)
)
periods = (simulation.lastRecord - simulation.startTime) \
    / simulation.recordsInterval
parameters = dict(startTime=simulation.startTime,
                  stopTime=simulation.lastRecord,
                  intervalTime=simulation.recordsInterval,
                  periods=periods)
with open(run_parameters, 'w') as f:
    json.dump(parameters, f)

# Change the status of the run.
run.status = 'Running'
run.save()
