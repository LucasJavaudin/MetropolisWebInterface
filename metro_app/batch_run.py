"""Implemented a External Script for the Batch Process.
Date: 20 December 2020
Author: Shubham"""

import os
import sys
import django
from django.utils import timezone

# Load the django website.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "metropolis_web_interface.settings")
django.setup()

from metro_app import models, functions

print('Starting script...')

# Read argument of the script call.
try:
    batch_id = int(sys.argv[1])
except IndexError:
    raise SystemExit('MetroArgError: This script must be executed with the id '
                     + 'of the batch has an argument.')

try:
    batch = models.Batch.objects.get(pk=batch_id)
except models.Batch.DoesNotExist:
    raise SystemExit('MetroDoesNotExist: No Batch object corresponding'
                     + ' to the given id.')

batch.status = 'Running'
batch.save()

simulation = batch.simulation

for i, batch_run in enumerate(batch.batchrun_set.all()):

    if batch_run.canceled:
        print('Run {} has been canceled, skipping...'.format(i+1))
        continue

    print('Importing files for run {}'.format(i+1))

    try:
        if batch_run.centroid_file:
            functions.object_import_function(
                batch_run.centroid_file.file, simulation, "centroid")

        if batch_run.crossing_file:
            functions.object_import_function(
                batch_run.crossing_file.file, simulation, "crossing")

        if batch_run.link_file:
            functions.object_import_function(
                batch_run.link_file.file, simulation, "link")

        if batch_run.function_file:
            functions.object_import_function(
                batch_run.function_file.file, simulation, "function")

        if batch_run.public_transit_file:
            functions.public_transit_import_function(
                batch_run.public_transit_file.file, simulation)

        if batch_run.traveler_file:
            functions.traveler_zip_file(
                simulation, batch_run.traveler_file)

        if batch_run.pricing_file:
            functions.pricing_import_function(
                batch_run.pricing_file.file, simulation)

        if batch_run.zip_file:
            functions.simulation_import(
                simulation, batch_run.zip_file)
    except Exception as e:
        print('Exception when importing files: {}'.format(e))
        batch_run.failed = True
        batch_run.save()
    else:
        print('Imports finished')

        batch_run.refresh_from_db()
        if batch_run.canceled:
            print('Run {} has been canceled, skipping...'.format(i+1))
            continue
        run_name = '{} - {}'.format(batch.name, batch_run.name)
        run = models.SimulationRun(name=run_name, simulation=simulation)
        run.save()
        batch_run.run = run
        batch_run.save()
        print('Starting run {}'.format(i+1))
        functions.run_simulation(run, background=False)
        print('Run finished')

batch.end_time = timezone.now()
batch.running_time = batch.end_time - batch.start_time
batch.status = "Finished"
batch.save()
print("Batch Completed")
