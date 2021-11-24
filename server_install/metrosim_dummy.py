#!/usr/bin/env python
"""
Simple script to replace the metrosim executable.
"""
import os
import sys
import time

# Execute the script with the virtualenv.
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
activate_this_file = os.path.join(basedir, 'venv/bin/activate_this.py')
with open(activate_this_file) as f:
    exec(f.read(), {'__file__': activate_this_file})

import django
from django.conf import settings

# Load the django website.
sys.path.append(basedir)
os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "metropolis_web_interface.settings")
django.setup()

from metro_app.models import Simulation, SimulationRun, SimulationMOEs
from metro_app.functions import get_query

# Read argument of the script call.
try:
    argfile = sys.argv[1]
except IndexError:
    raise SystemExit('MetroArgError: Metrosim must be executed with the '
                     + 'argfile of the SimulationRun has an argument.')

with open(argfile, 'r') as f:
    args = f.read().replace('"', '').split(' ')

    db_name = args[3]

    logfile = args[9]
    with open(logfile, 'w') as g:
        g.write('Metrosim is running.')

    outputdir = args[11]

    stopfile = args[13]

    simulation_id = int(args[15])
    run_id = int(args[17])

# Get the SimulationRun object of the argument.
try:
    run = SimulationRun.objects.get(pk=run_id)
except SimulationRun.DoesNotExist:
    raise SystemExit('MetroDoesNotExist: No SimulationRun object '
                     + 'corresponding to the given id.')

# Retrieve Simulation and Link objects.
simulation = run.simulation
links = get_query('link', simulation.id)

# Write dummy MOEs.
moes = SimulationMOEs(
    simulation=simulation.id,
    runid=run.id,
)
moes.save()

# Wait 2 minutes.
for i in range(30):
    if os.path.isfile(stopfile):
        break
    if i % 10 == 0:
        with open(logfile, 'a') as g:
            g.write('\n{} seconds remaining.'.format(30-i))
    time.sleep(1)

if not os.path.isfile(stopfile):
    # Write dummy output files.
    output_types = ['phi_in_H', 'phi_in_S', 'phi_out_H', 'phi_out_S',
                    'ttime_H', 'ttime_S']
    for output_type in output_types:
        outputfile = 'metrosim_net_arcs_{0}_{1}_{2!s}.txt'.format(
            output_type, db_name, simulation.id)
        with open(os.path.join(outputdir, outputfile), 'w') as g:
            g.write('{}\t0\t0'.format(links[0].id))
    if simulation.outputUsersTimes == 'true':
        outputfile = 'metrosim_users_{}_{}.txt'.format(
            db_name, simulation.id)
        with open(os.path.join(outputdir, outputfile), 'w') as g:
            g.write('')
    if simulation.outputUsersPaths == 'true':
        outputfile = 'metrosim_events_{}_{}.txt'.format(
            db_name, simulation.id)
        with open(os.path.join(outputdir, outputfile), 'w') as g:
            g.write('')

