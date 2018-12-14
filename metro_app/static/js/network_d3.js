// Default size depends on minNorm (min length of link)
var multSize = 1;
var networkSize;
// Links with more than maxLanes lanes have the same size than links with exactly maxLanes lanes
// multSize = 1 and maxLanes = 4 guarantee that no link is hidden because its origin and destination nodes are too large
var maxLanes = 4;

// Define zoom
var zoom = d3.zoom()
    .on("zoom", zoomed);

// Define drag
var drag = d3.drag()
    .on("start", dragstarted)
    .on("drag", dragged)
    .on("end", dragended);

// Call zoom function on main svg
var svg = d3.select("#main-svg")
    .attr("width", "100%")
    .attr("height", "100%")
  .append("g")
    .call(zoom);

// Create rectangle to manage pointer-events
var rect = svg.append("rect")
    .attr("width", "100%") 
    .attr("height", "100%")
    .style("fill", "none")
    .style("pointer-events", "all");

// Container where all elements of the graph are drawn
var container = svg.append("g");

// Define arrow heads
var defs = container.append('defs')
var marker = defs.selectAll('marker')
	.data(output.graph.edges)
	.enter()
	.append('marker')
	 .attr('id', function(d) { return 'marker_' + d.id})
	 .attr('viewBox', '0 -5 10 10')
	 .attr('refY', 0)
	 .attr('markerWidth', 2) // Arrow size
	 .attr('markerHeight', 3) // Arrow size
	 .attr('orient', 'auto')
	 .attr('xoverflow', 'visible')

var markerPaths = marker.append('svg:path')
			 .attr('d', 'M0,-5L10,0L0,5')

// Add links
var links = container.selectAll(".links")
		     .data(output.graph.edges)
		     .enter().append("g")
		     .attr("class", "links");

var lines = links.append("line")
   		 .attr('marker-end', function(d, i) { return 'url(#marker_' + d.id + ')'})
   		 .style("fill", "none")

// initial link color
drawLinks()

// Add label to links (on mouse over)
var linkLabels = links.append("title")
     		       .text(getLinkLabel);

// Add centroids
var centroids = container.selectAll(".centroid")
		     .data(output.graph.nodes.filter(function(n) { return n.centroid == 'true' }))
		     .enter().append("g")
		     .attr("class", "centroid");

var centroidCircles = centroids.append("circle")
		   .attr("cx", function(d) { return d.x; })
		   .attr("cy", function(d) { return -d.y; })

// Add crossings
var crossings = container.selectAll(".crossing")
		     .data(output.graph.nodes.filter(function(n) { return n.centroid == 'false' }))
		     .enter().append("g")
		     .attr("class", "crossing");

var crossingCircles = crossings.append("circle")
		   .attr("cx", function(d) { return d.x; })
		   .attr("cy", function(d) { return -d.y; })
		   .attr("fill", 'black');

// Add label to node (on mouse over)
var centroidLabels = centroids.append("title")
		       .text(getCentroidLabel);
var crossingLabels = crossings.append("title")
		       .text(getCrossingLabel);

// Set network size to initial value
setSize(multSize)

// Manage zoom level and center point
var mainGraph = document.getElementById('graph-container')
    mainGraphWidth = mainGraph.offsetWidth
    mainGraphHeight = mainGraph.offsetHeight
    center_x = (output.stats.x.min + output.stats.x.max) / 2
    center_y = -(output.stats.y.min + output.stats.y.max) / 2
    default_x = mainGraphWidth/2
    default_y = mainGraphHeight/2
zoom.translateBy(svg, default_x - center_x, default_y - center_y) // Initial center point

var graph_width = output.stats.x.max - output.stats.x.min // Nb pixels width required to show all graph
    graph_height = output.stats.y.max - output.stats.y.min // Nb pixels height required to show all graph
    zoomX = mainGraphWidth / graph_width // Min zoom required to show all graph width
    zoomY = mainGraphHeight / graph_height // Min zoom required to show all graph height
    minZoom = Math.min(zoomX, zoomY) // Min zoom required to show all graph

zoom.scaleTo(svg, minZoom/1.1) // Initial zoom
zoom.scaleExtent([minZoom/2, Infinity]) // Min and max zoom

function zoomed() {
  container.attr("transform", d3.event.transform);
}

function dragstarted(d) {
  d3.event.sourceEvent.stopPropagation();
  d3.select(this).classed("dragging", true);
}

function dragged(d) {
  d3.select(this).attr("cx", d.x = d3.event.x).attr("cy", d.y = d3.event.y);
}

function dragended(d) {
  d3.select(this).classed("dragging", false);
}

// Change zone colors and sizes according to what the user selected
function drawZones() {
	val = zoneSelector.value
	// Remove any previous legend
	d3.select('#centroidLegendSvg').remove();
	// Hide label
	zoneLabel.style.display = 'none'
	if (val == 'none'){ 
		// Default centroid radius is twice the radius of a crossing
		centroidCircles.attr("fill", "rgba(0, 0, 255, .8)");
		centroidCircles.attr("r", 2 * (maxLanes + 1) * networkSize);
	} else if (val == 'departures'){
		drawCentroidLegend(output.colorscales.departures, 0, output.stats.departures.max);
		centroidCircles.attr("fill", function(d) { return d.departures.colors });
		centroidCircles.attr("r", function(d) { return (1 + 2 * d.departures.values/output.stats.departures.max) * (maxLanes + 1) * networkSize});
	} else if (val == 'arrivals'){
		drawCentroidLegend(output.colorscales.arrivals, 0, output.stats.arrivals.max);
		centroidCircles.attr("fill", function(d) { return d.arrivals.colors });
		centroidCircles.attr("r", function(d) { return (1 + 2 * d.arrivals.values/output.stats.arrivals.max) * (maxLanes + 1) * networkSize});
	} else if (val == 'averages'){
		drawCentroidLegend(output.colorscales.averages, 0, output.stats.averages.max);
		centroidCircles.attr("fill", function(d) { return d.averages.colors });
		centroidCircles.attr("r", function(d) { return (1 + 2 * d.averages.values/output.stats.averages.max) * (maxLanes + 1) * networkSize});
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
		hsValue=hsSelector.value
		// Display or hide time slider
		if (selectorValue=='phi_in' || selectorValue=='phi_out' || selectorValue=='ttime'){
			sliderDiv.style = "visibility: visible!important"
			hssDiv.style = "visibility: visible!important"
		} else {
			sliderDiv.style = "visibility: hidden!important"
			hssDiv.style = "visibility: hidden!important";
		}
	}
	if (selectorValue == 'none'){
		lines.style("stroke", "rgba(255, 0, 0, .8)")
		markerPaths.attr('fill', 'rgba(255, 0, 0, .8)');
	} else if (selectorValue == 'lanes'){
		drawLinkLegend(output.colorscales.lanes, output.stats.lanes.min, output.stats.lanes.max);
		lines.style("stroke", function(d) { return d.lanes.colors});
		markerPaths.attr('fill', function(d) { return d.lanes.colors});
	} else if (selectorValue == 'length'){
		drawLinkLegend(output.colorscales.length, output.stats.length.min, output.stats.length.max);
		lines.style("stroke", function(d) { return d.length.colors});
		markerPaths.attr('fill', function(d) { return d.length.colors});
	} else if (selectorValue == 'speed'){
		drawLinkLegend(output.colorscales.speed, output.stats.speed.min, output.stats.speed.max);
		lines.style("stroke", function(d) { return d.speed.colors});
		markerPaths.attr('fill', function(d) { return d.speed.colors});
	} else if (selectorValue == 'capacity'){
		drawLinkLegend(output.colorscales.capacity, output.stats.capacity.min, output.stats.capacity.max);
		lines.style("stroke", function(d) { return d.capacity.colors});
		markerPaths.attr('fill', function(d) { return d.capacity.colors});
	} else if (selectorValue == 'type'){
		drawLinkLegend(output.colorscales.type, 0, output.stats.type.nb);
		lines.style("stroke", function(d) { return d.type.colors});
		markerPaths.attr('fill', function(d) { return d.type.colors});
	} else if (selectorValue == 'phi_in' && hsValue == 'h'){
		drawLinkLegend(results.colorscale, results.stats.phi_in_H.min, results.stats.phi_in_H.max);
		lines.style("stroke", function(d) { return results.phi_in_H.colors[d['id']][period]});
		markerPaths.attr('fill', function(d) { return results.phi_in_H.colors[d['id']][period]});
	} else if (selectorValue == 'phi_in' && hsValue == 's'){
		drawLinkLegend(results.colorscale, results.stats.phi_in_S.min, results.stats.phi_in_S.max);
		lines.style("stroke", function(d) { return results.phi_in_S.colors[d['id']][period]});
		markerPaths.attr('fill', function(d) { return results.phi_in_S.colors[d['id']][period]});
	} else if (selectorValue == 'phi_out' && hsValue == 'h'){
		drawLinkLegend(results.colorscale, results.stats.phi_out_H.min, results.stats.phi_out_H.max);
		lines.style("stroke", function(d) { return results.phi_out_H.colors[d['id']][period]});
		markerPaths.attr('fill', function(d) { return results.phi_out_H.colors[d['id']][period]});
	} else if (selectorValue == 'phi_out' && hsValue == 's'){
		drawLinkLegend(results.colorscale, results.stats.phi_out_S.min, results.stats.phi_out_S.max);
		lines.style("stroke", function(d) { return results.phi_out_S.colors[d['id']][period]});
		markerPaths.attr('fill', function(d) { return results.phi_out_S.colors[d['id']][period]});
	} else if (selectorValue == 'ttime' && hsValue == 'h'){
		drawLinkLegend(results.colorscale, results.stats.ttime_H.min, results.stats.ttime_H.max);
		lines.style("stroke", function(d) { return results.ttime_H.colors[d['id']][period]});
		markerPaths.attr('fill', function(d) { return results.ttime_H.colors[d['id']][period]});
	} else if (selectorValue == 'ttime' && hsValue == 's'){
		drawLinkLegend(results.colorscale, results.stats.ttime_S.min, results.stats.ttime_S.max);
		lines.style("stroke", function(d) { return results.ttime_S.colors[d['id']][period]});
		markerPaths.attr('fill', function(d) { return results.ttime_S.colors[d['id']][period]});
	}
}

function setSize(val) {
	multSize = val;
  	networkSize = output.stats.norm.min * multSize / 40;
	// Link width is equal to networkSize multiplied by the number of lanes (up to maxLanes)
	lines.style("stroke-width", function(d) { if(d.lanes < 4){ return networkSize * d.lanes } else { return 4 * networkSize } });
	// Crossing radius is equal to the width of the widest link + 1
	crossingCircles.attr("r", (maxLanes + 1) * networkSize);
	// Links are offset from the center of the nodes by half of the radius of a crossing
	lines.attr("x1", function(d) { return d.x1 + (maxLanes+1) * networkSize * d.dx / 2})
   	     .attr("x2", function(d) { return d.x2 + (maxLanes+1) * networkSize * d.dx / 2})
   	     .attr("y1", function(d) { return -(d.y1 - (maxLanes+1) * networkSize * d.dy / 2)})
   	     .attr("y2", function(d) { return -(d.y2 - (maxLanes+1) * networkSize * d.dy / 2)})
	// Change centroid size
	drawZones()
	// Arrow marker are arround the middle of the link
	// I do not understand how refX works but the following command do what I want to do
	marker.attr('refX', function(d) { return d.norm/(1.67*networkSize) });
}

function getCentroidLabel(d) {
	return d.name + '\n(' + d.x + ', ' + d.y + ')\nDepartures: ' + d.departures.values + '\nArrivals: ' + d.arrivals.values
}

function getCrossingLabel(d) {
	return d.name + '\n(' + d.x + ', ' + d.y + ')'
}

function getLinkLabel(d) {
	return d.name + '\nLanes: ' + d.lanes.values + '\nLength: ' + d.length.values + '\nSpeed: ' + d.speed.values + '\nType: ' + d.type.name + '\nCapacity: ' + d.capacity.values
}
