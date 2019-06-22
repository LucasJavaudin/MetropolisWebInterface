var mainGraph = document.getElementById('graph-container')
    mainGraphWidth = mainGraph.offsetWidth
    mainGraphHeight = mainGraph.offsetHeight
    mainGraphArea = mainGraphWidth * mainGraphHeight
    nbNodes = output.graph.nodes.length

// Links with more than maxLanes lanes have the same size than links with exactly maxLanes lanes
var maxLanes = 4;

// Instantiate sigma:
s = new sigma({
  graph: output.graph,
  renderer: {
    container: mainGraph,
    //type: 'canvas'
  },
  settings: {
    drawEdgeLabels: false,
    zoomMin: 0,
    zoomMax: Infinity,
  },
});

// Variables to update nodes and edges easily
var nodes = s.graph.nodes();
var edges = s.graph.edges();

// Change line width to be proportional to number of lanes
edges.forEach(function(e) { if(e.lanes < maxLanes) {e.size=e.lanes} else {e.size=100} });

// Set size
setSize(1)

// First draw for zones and links
drawZones('none')
drawLinks('none')

// Triger function when clicking on node or edge
s.bind("clickNode", function (event) { console.log(event.data.node.x, event.data.node.y) });
s.bind("clickEdge", function (event) { console.log(event.data.edge.size) });

function setSize(val) {
    multSize = val;
    size = multSize * (mainGraphArea / Math.sqrt(nbNodes)) / 100000;
    s.settings('minEdgeSize', .1*size);
    s.settings('maxEdgeSize', 10*size);
    s.settings('minNodeSize', 5*size);
    s.settings('maxNodeSize', 30*size);
    s.refresh();
}

// Change node colors according to what the user selected
function drawZones() {
	val = zoneSelector.value
	// Remove any previous legend
	d3.select('#centroidLegendSvg').remove();
	// Hide label
	zoneLabel.style.display = 'none'
	if (val == 'none'){ 
		nodes.forEach(function(n) { if (n.centroid == 'true') { n.color='rgba(0, 0, 255, .8)' } });
		nodes.forEach(function(n) { if (n.centroid == 'true'){n.size=500}else{n.size=1}});
		s.refresh();
	} else if (val == 'departures'){
		drawCentroidLegend(output.colorscales.departures, 0, output.stats.departures.max);

		nodes.forEach(function(n) { if (n.centroid == 'true') { n.color=n.departures.colors } });
		//nodes.forEach(function(n) { if (n.centroid == 'true') { n.size=n.departures.values } else { n.size=0 } });
		s.refresh();
	} else if (val == 'arrivals'){
		drawCentroidLegend(output.colorscales.arrivals, 0, output.stats.arrivals.max);
		nodes.forEach(function(n) { if (n.centroid == 'true') { n.color=n.arrivals.colors } });
		//nodes.forEach(function(n) { if (n.centroid == 'true') { n.size=n.arrivals.values } });
		s.refresh();
	} else if (val == 'averages'){
		drawCentroidLegend(output.colorscales.averages, 0, output.stats.averages.max);
		nodes.forEach(function(n) { if (n.centroid == 'true') { n.color=n.averages.colors } });
		//nodes.forEach(function(n) { if (n.centroid == 'true') { n.size=n.averages.values } });
		s.refresh();
	}
}

// Change link colors and sizes according to what the user selected
function drawLinks() {
	selectorValue=linkSelector.value
	// Remove any previous legend
	d3.select('#linkLegendSvg').remove();
	// Hide label
	linkLabel.style.display = 'none'
	if (typeof results !== 'undefined') {
		period=slider.value
		// hsValue=hsSelector.value
		// Display or hide time slider
		if (selectorValue=='phi_in' || selectorValue=='phi_out' || selectorValue=='ttime'){
			sliderDiv.style = "visibility: visible!important"
			// hssDiv.style = "visibility: visible!important"
		} else {
			sliderDiv.style = "visibility: hidden!important"
			// hssDiv.style = "visibility: hidden!important";
		}
	}
	if (selectorValue == 'none'){
		edges.forEach(function(e) { e.color='rgb(255, 0, 0)' });
		s.refresh();
	} else if (selectorValue == 'lanes'){
		drawLinkLegend(output.colorscales.lanes, output.stats.lanes.min, output.stats.lanes.max);
		edges.forEach(function(e) { e.color=e.lanes.colors });
		s.refresh();
	} else if (selectorValue == 'length'){
		drawLinkLegend(output.colorscales.length, output.stats.length.min, output.stats.length.max);
		edges.forEach(function(e) { e.color=e.length.colors });
		s.refresh();
	} else if (selectorValue == 'speed'){
		drawLinkLegend(output.colorscales.speed, output.stats.speed.min, output.stats.speed.max);
		edges.forEach(function(e) { e.color=e.speed.colors });
		s.refresh();
	} else if (selectorValue == 'capacity'){
		drawLinkLegend(output.colorscales.capacity, output.stats.capacity.min, output.stats.capacity.max);
		edges.forEach(function(e) { e.color=e.capacity.colors });
		s.refresh();
	} else if (selectorValue == 'type'){
		drawLinkLegend(output.colorscales.type, 0, output.stats.type.nb);
		edges.forEach(function(e) { e.color=e.type.colors });
		s.refresh();
	} else if (selectorValue == 'phi_in'){
		drawLinkLegend(results.colorscale, results.stats.phi_in_H.min, results.stats.phi_in_H.max);
		edges.forEach(function(e) { e.color=results.phi_in_H.colors[e.id][period] });
		s.refresh();
	} else if (selectorValue == 'ttime'){
		drawLinkLegend(results.colorscale, results.stats.ttime_H.min, results.stats.ttime_H.max);
		edges.forEach(function(e) { e.color=results.ttime_H.colors[e.id][period] });
		s.refresh();
	/*
	} else if (selectorValue == 'phi_in' && hsValue == 's'){
		drawLinkLegend(results.colorscale, results.stats.phi_in_S.min, results.stats.phi_in_S.max);
		edges.forEach(function(e) { e.color=results.phi_in_S.colors[e.id][period] });
		s.refresh();
	} else if (selectorValue == 'phi_out' && hsValue == 'h'){
		drawLinkLegend(results.colorscale, results.stats.phi_out_H.min, results.stats.phi_out_H.max);
		edges.forEach(function(e) { e.color=results.phi_out_H.colors[e.id][period] });
		s.refresh();
	} else if (selectorValue == 'phi_out' && hsValue == 's'){
		drawLinkLegend(results.colorscale, results.stats.phi_out_S.min, results.stats.phi_out_S.max);
		edges.forEach(function(e) { e.color=results.phi_out_S.colors[e.id][period] });
		s.refresh();
	} else if (selectorValue == 'ttime' && hsValue == 'h'){
		drawLinkLegend(results.colorscale, results.stats.ttime_H.min, results.stats.ttime_H.max);
		edges.forEach(function(e) { e.color=results.ttime_H.colors[e.id][period] });
		s.refresh();
	} else if (selectorValue == 'ttime' && hsValue == 's'){
		drawLinkLegend(results.colorscale, results.stats.ttime_S.min, results.stats.ttime_S.max);
		edges.forEach(function(e) { e.color=results.ttime_S.colors[e.id][period] });
		s.refresh();
	*/
	}
}
