/**
 * Network view
 * @author Lucas Javaudin
 *
 * This file contains the script that small networks (D3) and large network (sigma) have in common.
 * In particular, the scripts manage the controls and the legends.
 */

// Ensure that the legend bars fill the page when window size is updated
redraw();
$( window ).resize(redraw);

// Register some html elements
var zoneSelector = document.getElementById('zoneSelector')
var linkSelector = document.getElementById("linkSelector");
var zoneLabel = document.getElementById("zoneLabel")
var linkLabel = document.getElementById("linkLabel")

// Size slider changes multSize
var sizeSlider = document.getElementById("sizeSlider");
var sizeOutput = document.getElementById("sizeValue");

// Update slider value on input
sizeOutput.innerHTML = '' + sizeSlider.value + ' %';
sizeSlider.oninput = function() {
	// Change slider value
	sizeOutput.innerHTML = '' + this.value + ' %';
	multSize = this.value/100;
	setSize(multSize);
}

function drawCentroidLegend(colorscale, min, max) {
	// Show label
	zoneLabel.style.display = 'block'

	var legendWidth = 100
	    legendMargin = 10
	    legendLength = document.getElementById('legend-zones-container').offsetHeight - 2*legendMargin
	    legendIntervals = Object.keys(colorscale).length
	    legendScale = legendLength/legendIntervals

	// Add legend
	var legendSvg = d3.select('#legend-zones-svg')
				.append('g')
				.attr("id", "centroidLegendSvg");

	var bars = legendSvg.selectAll(".bars")
	    .data(d3.range(legendIntervals), function(d) { return d})
	  .enter().append("rect")
	    .attr("class", "bars")
	    .attr("x", 0)
	    .attr("y", function(d, i) { return legendMargin + legendScale * (legendIntervals - i - 1); })
	    .attr("height", legendScale)
	    .attr("width", legendWidth-50)
	    .style("fill", function(d) { return colorscale[d]; })

	// create a scale and axis for the legend
	var legendAxis = d3.scaleLinear()
	    .domain([min, max])
	    .range([legendLength, 0]);

	legendSvg.append("g")
		 .attr("class", "legend axis")
		 .attr("transform", "translate(" + (legendWidth - 50) + ", " + legendMargin + ")")
		 .call(d3.axisRight().scale(legendAxis).ticks(10))
}

function drawLinkLegend(colorscale, min, max) {
	// Show label
	linkLabel.style.display = 'block'

	var legendWidth = 100
	    legendMargin = 10
	    legendLength = document.getElementById('legend-links-container').offsetHeight - 2*legendMargin
	    legendIntervals = Object.keys(colorscale).length
	    legendScale = legendLength/legendIntervals

	// Add legend
	var legendSvg = d3.select('#legend-links-svg')
				.append('g')
				.attr("id", "linkLegendSvg");

	var bars = legendSvg.selectAll(".bars")
	    .data(d3.range(legendIntervals), function(d) { return d})
	  .enter().append("rect")
	    .attr("class", "bars")
	    .attr("x", 0)
	    .attr("y", function(d, i) { return legendMargin + legendScale * (legendIntervals - i - 1); })
	    .attr("height", legendScale)
	    .attr("width", legendWidth-50)
	    .style("fill", function(d) { return colorscale[d] })

	// create a scale and axis for the legend
	var legendAxis = d3.scaleLinear()
	    .domain([min, max])
	    .range([legendLength, 0]);

	legendSvg.append("g")
		 .attr("class", "legend axis")
		 .attr("transform", "translate(" + (legendWidth - 50) + ", " + legendMargin + ")")
		 .call(d3.axisRight().scale(legendAxis).ticks(10))
}

function redraw() {
	var controlsHeight = document.getElementById('controls').offsetHeight;
	var labelHeight = document.getElementById('zoneLabel').offsetHeight;
	var totalHeight = document.body.offsetHeight;
	var height = totalHeight - labelHeight - controlsHeight - 50;
	document.getElementById('legend-zones-container').style='height:'+height+'px';
	document.getElementById('legend-links-container').style='height:'+height+'px';
}

if (typeof results !== 'undefined') {
	var sliderDiv = document.getElementById("sliderDiv");
	var slider = document.getElementById("timeSlider");
	var sliderOutput = document.getElementById("slideValue");

	// Update slider value on input
	sliderOutput.innerHTML = valueToTime(slider.value);
	// Slider goes from 0 to the nb of record periods minus 1
	slider.max = parameters.periods-1;

	slider.oninput = function() {
		// Change slider value
		sliderOutput.innerHTML = valueToTime(this.value);
		drawLinks();
	}

	function valueToTime(val) {
		// This function converts a standard value 0, 1, ... to a Metropolis time 6:00 AM, 6:10 AM.
		// 1. Convert value to number of minutes after midnight.
		val = parameters.startTime + val * parameters.intervalTime;
		// 2. Convert minutes to a time string.
		var hours = Math.floor(val / 60);
		var minutes = val % 60;
		if(val >= 780){ hours = hours-12 }
		if(val < 60){ hours=hours+12 }
		hours = "" + hours;
		if(minutes < 10){ minutes = "0" + minutes }else{ minutes = "" + minutes }
		var string = hours + ":" + minutes + " ";
		if(val < 720 || val >= 1440){ string += "AM" }else{ string += "PM" }
		return string
	}

	if (largeNetwork == false) {
		var hssDiv = document.getElementById("hssDiv")
		var hsSelector = document.getElementById("HSSelector")
	}
}
