/* Free basemap adapter. MapLibre is loaded lazily so the task table survives SDK failures. */
(function (global) {
  const SDK_URL = 'https://unpkg.com/maplibre-gl@6.16.0/dist/maplibre-gl.mjs';

  function validCoordinates(latitude, longitude) {
    return Number.isFinite(latitude) && Number.isFinite(longitude) &&
      latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
  }

  class TrackerMap {
    constructor({container, styleUrl, center = [71.47, 51.16], onSelect = () => {}, onStatus = () => {},
                 loadLibrary = () => import(SDK_URL)}) {
      this.container = container;
      this.styleUrl = styleUrl;
      this.center = center;
      this.onSelect = onSelect;
      this.onStatus = onStatus;
      this.tasks = [];
      this.markers = [];
      this.selection = null;
      this.selectionMarker = null;
      this.disposed = false;
      this.ready = this.initialize(loadLibrary);
    }

    async initialize(loadLibrary) {
      try {
        this.library = await loadLibrary();
        if (this.disposed) return false;
        this.map = new this.library.Map({
          container: this.container, style: this.styleUrl, center: this.center,
          zoom: 12, renderWorldCopies: false, attributionControl: true
        });
        this.map.addControl(new this.library.NavigationControl(), 'top-right');
        this.map.on('load', () => this.onStatus('Карта готова. Нажмите на нужное место.'));
        this.map.on('error', () => this.onStatus('Не удалось загрузить часть карты. Координаты можно ввести вручную.'));
        this.map.on('click', event => {
          const longitude = ((event.lngLat.lng + 180) % 360 + 360) % 360 - 180;
          this.select(event.lngLat.lat, longitude);
        });
        this.setTasks(this.tasks);
        if (this.selection) this.drawSelection();
        if (this.focusPoint) this.map.flyTo({center:this.focusPoint,zoom:16});
        return true;
      } catch (error) {
        if (!this.disposed) this.onStatus('Карта недоступна. Задачи и ручной ввод координат продолжают работать.');
        return false;
      }
    }

    clearTasks() {
      this.tasks = [];
      for (const marker of this.markers) {
        const popup = marker.getPopup();
        if (popup) popup.remove();
        marker.remove();
      }
      this.markers = [];
    }

    setTasks(tasks) {
      this.clearTasks();
      this.tasks = tasks;
      if (!this.map || this.disposed) return;
      for (const task of tasks) {
        if (!validCoordinates(task.latitude, task.longitude)) continue;
        const popup = new this.library.Popup({offset: 25}).setText(`Task ${task.id}: ${task.description || 'N/A'}`);
        const marker = new this.library.Marker({color: '#1978e5'})
          .setLngLat([task.longitude, task.latitude]).setPopup(popup).addTo(this.map);
        // Opening an existing task must not select a new task destination.
        marker.getElement().addEventListener('click', event => event.stopPropagation());
        this.markers.push(marker);
      }
    }

    select(latitude, longitude) {
      if (!validCoordinates(latitude, longitude) || this.disposed) return false;
      this.selection = {latitude: Number(latitude.toFixed(6)), longitude: Number(longitude.toFixed(6))};
      this.drawSelection();
      this.onSelect(this.selection);
      return true;
    }

    focus(latitude, longitude) {
      if (!this.select(latitude, longitude)) return false;
      this.focusPoint = [longitude, latitude];
      if (this.map) this.map.flyTo({center: this.focusPoint, zoom: 16});
      return true;
    }

    drawSelection() {
      if (!this.map) return;
      if (!this.selectionMarker) {
        this.selectionMarker = new this.library.Marker({color: '#23934a', draggable: true})
          .setLngLat([this.selection.longitude, this.selection.latitude]).addTo(this.map);
        this.selectionMarker.on('dragend', () => {
          const point = this.selectionMarker.getLngLat();
          const longitude = ((point.lng + 180) % 360 + 360) % 360 - 180;
          this.select(point.lat, longitude);
        });
      }
      this.selectionMarker.setLngLat([this.selection.longitude, this.selection.latitude]);
    }

    clearSelection() {
      if (this.selectionMarker) this.selectionMarker.remove();
      this.selectionMarker = null;
      this.selection = null;
      this.focusPoint = null;
      this.onSelect(null);
    }

    destroy() {
      this.disposed = true;
      this.clearTasks();
      this.clearSelection();
      if (this.map) this.map.remove();
    }
  }

  global.TrackerMap = TrackerMap;
})(window);
