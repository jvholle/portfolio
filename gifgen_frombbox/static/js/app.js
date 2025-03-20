// Initialize the map
var map = L.map('map').setView([51.505, -0.09], 13);

// Add a tile layer to the map (OpenStreetMap tiles)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19
}).addTo(map);

// Initialize the FeatureGroup to store editable layers
var drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

// Initialize the draw control and pass it the FeatureGroup of editable layers
var drawControl = new L.Control.Draw({
    edit: {
        featureGroup: drawnItems
    },
    draw: {
        polygon: false,
        polyline: false,
        circle: false,
        marker: false,
        rectangle: true
    }
});
map.addControl(drawControl);

// Function to display data in a table
function displayDataInTable(geojsonData) {
    const tableContainer = document.getElementById('table-container');
    const features = geojsonData;  // geojsonData.features;
	// console.log(typeof features);
    if (!features || features.length === 0) {
        tableContainer.innerHTML = '<p>No data available</p>';
        return;
    }
    let tableHTML = '<table>';
    tableHTML += '<thead><tr><th>ID</th><th>Properties</th><th>Geometry</th><th>Links</th><th>Assets</th><th>BBox</th></tr></thead>';
    tableHTML += '<tbody>';
    features.forEach(feature => {
        tableHTML += '<tr>';
        tableHTML += `<td>${feature.id}</td>`;
        tableHTML += `<td>${JSON.stringify(feature.properties)}</td>`;
        tableHTML += `<td>${JSON.stringify(feature.geometry)}</td>`;
        tableHTML += `<td>${JSON.stringify(feature.links)}</td>`;
        // tableHTML += `<td>${JSON.stringify(feature.assets)}</td>`;
        tableHTML += `<td>${JSON.stringify(feature.bbox)}</td>`;
        tableHTML += '</tr>';
    });
    tableHTML += '</tbody></table>';
    tableContainer.innerHTML = tableHTML;
}

// Event listener for when a shape (rectangle) is drawn
map.on(L.Draw.Event.CREATED, function (event) {
    var layer = event.layer;
    drawnItems.addLayer(layer);

    // Get the bounds of the drawn rectangle
    var bounds = layer.getBounds();
    var northEast = bounds.getNorthEast();
    var southWest = bounds.getSouthWest();

    // Display the bounding box coordinates
    //var bboxCoordinates = `North-East: ${northEast.lat}, ${northEast.lng} <br> South-West: ${southWest.lat}, ${southWest.lng}`;
	//var bbox = [bounds.getWest, bounds.getSouth, bounds.getEast, bounds.getNorth]
	var bbox = [southWest.lng, southWest.lat, northEast.lng, northEast.lat]
	document.getElementById('bbox').innerHTML = 'Returned Bbox: ' + bbox;  // bboxCoordinates;
	//return [bbox]
	
	// ===
	// Upon draw bbox on map, pass bbox to flask script for STAC query and then extract section large image display.  	
	fetch('/get_bbox', { 
	  method: 'POST',
	  headers: {
		'Content-Type': 'application/json'
	  },
	  body: JSON.stringify({data: bbox})  // 'selected_item'
	})
	.then(response => response.text())
	.then(result => {
	  console.log('STAC query result: ', result); 
	  gjson = L.geoJSON(JSON.parse(result)).addTo(map);  // Need to parse the json returned from Flask.
	
	  // Add the geojson data to a table
	  displayDataInTable(JSON.parse(result));

      /* 		gjson.eachLayer(function (layer) {
			if('id' in layer.feature){
				layer.bindPopup(layer.feature.id, 
				{permanent: true}).openPopup();  // .addTo(Map)
			} else {
				layer.bindPopup(layer.feature.properties.name, {permanent: true}).openPopup();  // offset; add where?
			}
		});  */
	})
	.catch(error => {
	  console.error('Error:', error);
	});
});

// Add callback to get recently generated gif/tiff within directory. **
document.getElementById("dl_images").addEventListener("click", function() {
    fetch("/download-img", {
        method: "POST", // Or GET, depending on your needs
        // Add any headers or body data as needed
    })
    .then(response => response.json()) // Assuming the response is JSON
    .then(data => {
        // Do something with the response data
        console.log(data);
    })
    .catch(error => {
        console.error("Error:", error);
    });
});

// Download csv from Flask as bytes.io object; ref, just dl func: https://www.geeksforgeeks.org/how-to-create-and-download-csv-file-in-javascript/
const download = function (data) {		  
	// Creating a Blob for having a csv file format and passing the data with type
	const blob = new Blob([data], { type: 'image/gif' });  // type for image/gif
  
	// Creating an object for downloading url
	const url = window.URL.createObjectURL(blob)
  
	// Creating an anchor(a) tag of HTML
	const a = document.createElement('a')
  
	// Passing the blob downloading url 
	a.setAttribute('href', url)

	// Setting the anchor tag attribute for downloading and passing the download file name
	a.setAttribute('download', 'gif_file_' + date.toString() + '.gif');
  
	// Performing a download with click
	a.click()
}
  
// function to Download csv of vehicles/platforms upon button click 	
const expgif = function() {
	fetch('/download-gif', { 
	  method: 'POST',
	  headers: {
		'Content-Type': 'application/json'
	  },
	  body: JSON.stringify({data: secInput})  // 'selected_item'
	})
	.then(response => response.text())
	.then(result => {
	  console.log(secInput);  //(result);
	  <!-- pass csv content to download function -->
	  download(result);
	})
	.catch(error => {
	  console.error('Error:', error);
	});
}
