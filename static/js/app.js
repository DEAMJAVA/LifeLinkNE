// Captures live GPS into a single "lat, lon" hidden input (used at registration,
// mirroring the original app's separate exact_location vs home_location fields).
function captureGeolocation(hiddenInput, statusEl) {
  if (!navigator.geolocation) {
    if (statusEl) statusEl.textContent = "Location unavailable on this device.";
    return;
  }
  navigator.geolocation.getCurrentPosition(
    function (pos) {
      hiddenInput.value = pos.coords.latitude + ", " + pos.coords.longitude;
      if (statusEl) statusEl.textContent = "Live location captured.";
    },
    function () {
      if (statusEl) statusEl.textContent = "Location permission denied — your home location will be used instead.";
    }
  );
}

// Captures live GPS into two separate hidden inputs (lat, lon) -- used on
// the SOS / blood donation forms.
function captureGeolocation2(latInput, lonInput, statusEl) {
  if (!navigator.geolocation) {
    if (statusEl) statusEl.textContent = "Location unavailable on this device.";
    return;
  }
  navigator.geolocation.getCurrentPosition(
    function (pos) {
      latInput.value = pos.coords.latitude;
      lonInput.value = pos.coords.longitude;
      if (statusEl) statusEl.textContent = "Live location captured.";
    },
    function () {
      if (statusEl) statusEl.textContent = "Location permission denied — your account's saved location will be used instead.";
    }
  );
}

// Renders a small Leaflet map into every element with class "map" that has
// data-lat/data-lon attributes.
function initMaps() {
  document.querySelectorAll(".map").forEach(function (el) {
    if (el.dataset.initialized) return;
    var lat = parseFloat(el.dataset.lat);
    var lon = parseFloat(el.dataset.lon);
    if (isNaN(lat) || isNaN(lon)) { el.textContent = "No location"; return; }
    el.dataset.initialized = "1";
    var map = L.map(el, { zoomControl: false, attributionControl: false }).setView([lat, lon], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
    }).addTo(map);
    L.marker([lat, lon]).addTo(map);
  });
}

// Filters the disaster-type <select> by the chosen severity bucket, on the
// "Report a Disaster" form.
function filterDisasterOptions(severitySelect, disasterSelect) {
  var allOptions = Array.prototype.slice.call(disasterSelect.options);

  function apply() {
    var sev = severitySelect.value;
    allOptions.forEach(function (opt) {
      if (!opt.value) { opt.hidden = false; return; }
      opt.hidden = sev !== "All" && opt.dataset.severity !== sev;
    });
    var current = disasterSelect.selectedOptions[0];
    if (current && current.hidden) disasterSelect.value = "";
  }

  severitySelect.addEventListener("change", apply);
  apply();
}

// Renders a green->yellow->red heatmap of disaster report density/severity
// over Northeast India. `points` is an array of [lat, lon, weight] triples
// (weight scales with disaster severity, and overlapping points from
// multiple reports in the same area stack to push the color further
// toward red).
function initHeatmap(containerId, points, center, zoom) {
  var el = document.getElementById(containerId);
  if (!el) return;
  var map = L.map(el).setView(center, zoom || 7);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
  }).addTo(map);

  if (!points || points.length === 0) {
    L.control.attribution({ prefix: false }).addTo(map);
    return;
  }

  L.heatLayer(points, {
    radius: 45,
    blur: 35,
    maxZoom: 10,
    max: 3,
    gradient: {
      0.0: "#2ecc71",  // green -- low intensity
      0.4: "#f1c40f",  // yellow
      0.7: "#f1a208",  // orange
      1.0: "#e74c3c",  // red -- high intensity
    },
  }).addTo(map);
}

document.addEventListener("click", function (e) {
  var dropdown = document.getElementById("user-dropdown");
  if (!dropdown) return;
  var toggle = document.querySelector(".user-toggle");
  if (dropdown.classList.contains("open") && e.target !== toggle) {
    dropdown.classList.remove("open");
  }
});
