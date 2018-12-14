import numpy as np
import matplotlib.pyplot as plt

from django.db.models import Sum

from .models import *

def get_arrivals_departures(simulation):
    # Get some objects.
    centroids = Centroid.objects.filter(
            network__supply__scenario__simulation=simulation
    )
    demand_segments = DemandSegment.objects.filter(
            demand=simulation.scenario.demand
    )
    matrices = Matrices.objects.filter(demandsegment__in=demand_segments)
    departures_values = []
    arrivals_values = []
    for centroid in centroids:
        departures = Matrix.objects.filter(p=centroid, matrices__in=matrices)
        arrivals = Matrix.objects.filter(q=centroid, matrices__in=matrices)
        if departures.count():
            departures_values.append(departures.aggregate(Sum('r'))['r__sum'])
        else:
            departures_values.append(0)
        if arrivals.count():
            arrivals_values.append(arrivals.aggregate(Sum('r'))['r__sum'])
        else:
            arrivals_values.append(0)
    return departures_values, arrivals_values

def build_colorscale(values, cmap):
    """Convert a numpy array of values to a list of colors using a color map.

    Return a list of colors, a dictionary with stats and a color scale.
    """
    transparency = .8
    # Compute min, max and average.
    min_val = np.min(values)
    max_val = np.max(values)
    ave_val = np.mean(values)
    if min_val == max_val:
        if min_val == 0:
            # The color scale goes from -1 to 1.
            min_val = -1
            max_val = 1
        else:
            # The color scale starts at 0, all values are in the middle of
            # the color scale.
            min_val = 0
            max_val *= 2
    # Create a dictionary with descriptive statistics.
    stats = {'min': min_val, 'max': max_val, 'average': ave_val}
    # Compute the list of colors.
    values = (values - min_val) / (max_val - min_val)
    colors = [cmap(val) for val in values]
    colors = ['rgba({0}, {1}, {2}, {3})'.format(int(color[0]*255),
                                                int(color[1]*255),
                                                int(color[2]*255),
                                                transparency)
              for color in colors]
    # Compute the color scale.
    size = 500
    colorscale_values = np.arange(0, size, 1)
    colorscale = [cmap(val/(size-1)) for val in colorscale_values]
    colorscale = ['rgba({0}, {1}, {2}, {3})'.format(color[0]*255, color[1]*255,
                                                    color[2]*255, transparency)
                  for color in colorscale]
    return stats, colors, colorscale

def build_qualitative_colorscale(ids, names):
    transparency = 0.8
    n = len(ids)
    values = np.arange(0, n, 1)
    stats = {'nb': n, 'names': names}
    colors = dict()
    colorscale = dict()
    if n <= 10:
        # Use a qualitative color map with 10 colors.
        cmap = plt.get_cmap('tab10')
        for (i, id) in enumerate(ids):
            color = cmap(i)
            colors[id] = 'rgb({0}, {1}, {2}, {3})'.format(int(color[0]*255),
                                                          int(color[1]*255),
                                                          int(color[2]*255),
                                                          transparency)
            colorscale[i] = 'rgb({0}, {1}, {2})'.format(color[0]*255,
                                                        color[1]*255,
                                                        color[2]*255)
    else:
        # Use a sequential color map.
        cmap = plt.get_cmap('nipy_spectral')
        for (i, id) in enumerate(ids):
            color = cmap(i/(n-1))
            colors[id] = 'rgb({0}, {1}, {2})'.format(color[0]*255,
                                                     color[1]*255,
                                                     color[2]*255)
            colorscale[i] = 'rgb({0}, {1}, {2})'.format(color[0]*255,
                                                        color[1]*255,
                                                        color[2]*255)
    return stats, colors, colorscale

def network_output(simulation, large_network):
    output = dict()
    output['stats'] = dict()
    output['colorscales'] = dict()
    output['graph'] = dict()

    # Get a color map from matplotlib.
    cmap = plt.get_cmap('YlGnBu')

    centroids = Centroid.objects.filter(
            network__supply__scenario__simulation=simulation
    )
    # Retrieve departures and arrivals at each centroid.
    departures, arrivals = get_arrivals_departures(simulation)
    departures = np.array(departures, dtype=float)
    arrivals = np.array(arrivals, dtype=float)
    averages = (departures + arrivals) / 2
    # Compute stats, colors and colorscales.
    stats, departures_colors, colorscale = build_colorscale(departures, cmap)
    output['stats']['departures'] = stats
    output['colorscales']['departures'] = colorscale
    stats, arrivals_colors, colorscale = build_colorscale(arrivals, cmap)
    output['stats']['arrivals'] = stats
    output['colorscales']['arrivals'] = colorscale
    stats, averages_colors, colorscale = build_colorscale(averages, cmap)
    output['stats']['averages'] = stats
    output['colorscales']['averages'] = colorscale
    # Build dictionary of attributes for the centroids.
    if large_network:
        centroid_nodes = [
                {
                    'id': centroid.id, 'x': centroid.x, 'y': -centroid.y,
                    'name': centroid.name, 'centroid': 'true',
                    'departures': {'values': departures[i],
                                   'colors': departures_colors[i]},
                    'arrivals': {'values': arrivals[i],
                                 'colors': arrivals_colors[i]},
                    'averages': {'values': averages[i],
                                 'colors': averages_colors[i]}
                }
                for (i, centroid) in enumerate(centroids)
        ]
    else:
        centroid_nodes = [
                {
                    'id': centroid.id, 'x': centroid.x, 'y': centroid.y,
                    'name': centroid.name, 'centroid': 'true',
                    'departures': {'values': departures[i],
                                   'colors': departures_colors[i]},
                    'arrivals': {'values': arrivals[i],
                                 'colors': arrivals_colors[i]},
                    'averages': {'values': averages[i],
                                 'colors': averages_colors[i]}
                }
                for (i, centroid) in enumerate(centroids)
        ]
    output['graph']['nodes'] = centroid_nodes

    crossings = Crossing.objects.filter(
            network__supply__scenario__simulation=simulation
    )
    if large_network:
        crossing_nodes = [
                {
                    'id': crossing.id, 'x': crossing.x, 'y': -crossing.y, 
                    'name': crossing.name, 'centroid': 'false'
                }
                for crossing in crossings
        ]
    else:
        crossing_nodes = [
                {
                    'id': crossing.id, 'x': crossing.x, 'y': crossing.y, 
                    'name': crossing.name, 'centroid': 'false'
                }
                for crossing in crossings
        ]
    output['graph']['nodes'] += crossing_nodes

    links = Link.objects.filter(
            network__supply__scenario__simulation=simulation
    )
    # Compute stats, colors and colorscales for the attributes of the link.
    lanes = np.array(links.values_list('lanes', flat=True))
    stats, lanes_colors, colorscale = build_colorscale(lanes, cmap)
    output['stats']['lanes'] = stats
    output['colorscales']['lanes'] = colorscale
    length = np.array(links.values_list('length', flat=True))
    stats, length_colors, colorscale = build_colorscale(length, cmap)
    output['stats']['length'] = stats
    output['colorscales']['length'] = colorscale
    speed = np.array(links.values_list('speed', flat=True))
    stats, speed_colors, colorscale = build_colorscale(speed, cmap)
    output['stats']['speed'] = stats
    output['colorscales']['speed'] = colorscale
    capacity = np.array(links.values_list('capacity', flat=True))
    stats, capacity_colors, colorscale = build_colorscale(capacity, cmap)
    output['stats']['capacity'] = stats
    output['colorscales']['capacity'] = colorscale
    # Instead of returning the id of the function for each link, we return a
    # pseudo-id which is between 0 and the number of function minus 1.
    function_ids = list(np.unique(links.values_list('vdf_id', flat=True)))
    function_names = list(np.unique(links.values_list('vdf__name', flat=True)))
    stats, type_colors, colorscale = build_qualitative_colorscale(
        function_ids, function_names
    )
    output['stats']['type'] = stats
    output['colorscales']['type'] = colorscale
    if large_network:
        link_edges = [
                (
                    {
                        'source': link.origin, 'target': link.destination, 
                        'name': link.name, 'id': link.id, 
                        'lanes': {'values': lanes[i], 'colors': lanes_colors[i]},
                        'length': {'values': length[i], 'colors': length_colors[i]},
                        'speed': {'values': speed[i], 'colors': speed_colors[i]},
                        'capacity': {'values': capacity[i],
                                     'colors': capacity_colors[i]},
                        'type': {'name': link.vdf.name,
                                 'colors': type_colors[link.vdf.id]},
                        'size': 1
                    }
                )
                for i, link in enumerate(links)
        ]
    else:
        link_edges = []
        for (i, link) in enumerate(links):
            # Find origin and destination nodes.
            try:
                origin = Crossing.objects.get(pk=link.origin)
            except Crossing.DoesNotExist:
                origin = Centroid.objects.get(pk=link.origin)
            try:
                destination = Crossing.objects.get(pk=link.destination)
            except Crossing.DoesNotExist:
                destination = Centroid.objects.get(pk=link.destination)
            # Get coordinates.
            x1 = origin.x
            x2 = destination.x
            y1 = origin.y
            y2 = destination.y
            # Get the link vector and normalize it.
            dx = x2 - x1
            dy = y2 - y1
            delta = np.array([dx, dy])
            norm = np.linalg.norm(delta)
            # Ignore 'dummy' links.
            if norm != 0:
                delta /= norm
                # Reverse the vector.
                delta = delta[::-1]
                dx, dy = delta
                link_edge = {
                        'source': link.origin, 'target': link.destination, 
                        'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2, 'dx': dx, 'dy': dy,
                        'name': link.name, 'id': link.id, 'norm': norm,
                        'lanes': {'values': lanes[i], 'colors': lanes_colors[i]},
                        'length': {'values': length[i], 'colors': length_colors[i]},
                        'speed': {'values': speed[i], 'colors': speed_colors[i]},
                        'capacity': {'values': capacity[i],
                                     'colors': capacity_colors[i]},
                        'type': {'name': link.vdf.name,
                                 'colors': type_colors[link.vdf.id]}
                }
                link_edges.append(link_edge)
    output['graph']['edges'] = link_edges

    # Compute more descriptive statistics.
    min_x = np.min(centroids.values_list('x', flat=True))
    max_x = np.max(centroids.values_list('x', flat=True))
    min_x = min(min_x, np.min(crossings.values_list('x', flat=True)))
    max_x = max(max_x, np.max(crossings.values_list('x', flat=True)))
    min_y = np.min(centroids.values_list('y', flat=True))
    max_y = np.max(centroids.values_list('y', flat=True))
    min_y = min(min_y, np.min(crossings.values_list('y', flat=True)))
    max_y = max(max_y, np.max(crossings.values_list('y', flat=True)))
    output['stats']['x'] = {'min': min_x, 'max': max_x}
    output['stats']['y'] = {'min': min_y, 'max': max_y}
    if not large_network:
        min_norm = min(output['graph']['edges'],
                       key=lambda x:x['norm'])['norm']
        max_norm = max(output['graph']['edges'],
                       key=lambda x:x['norm'])['norm']
        ave_norm = np.mean([x['norm'] for x in output['graph']['edges']])
        output['stats']['norm'] = {'min': min_norm, 'max': max_norm,
                                   'ave': ave_norm}

    return output
