import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

interface HospitalMapProps {
  userLocation?: { latitude: number; longitude: number };
  hospitalLocation: { latitude: number; longitude: number };
  hospitalName: string;
}

export function HospitalMap({ userLocation, hospitalLocation, hospitalName }: HospitalMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const apiKey = import.meta.env.VITE_AWS_LOCATION_API_KEY;
    const region = import.meta.env.VITE_AWS_LOCATION_REGION || "us-east-1";
    const style = import.meta.env.VITE_AWS_LOCATION_MAP_STYLE || "Standard";
    const colorScheme = import.meta.env.VITE_AWS_LOCATION_COLOR_SCHEME || "Light";

    // Initialize map
    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: `https://maps.geo.${region}.amazonaws.com/v2/styles/${style}/descriptor?key=${apiKey}&color-scheme=${colorScheme}`,
      center: [hospitalLocation.longitude, hospitalLocation.latitude],
      zoom: 13,
    });

    // Add navigation controls
    map.current.addControl(new maplibregl.NavigationControl(), "top-right");

    // Add hospital marker
    new maplibregl.Marker({ color: "#3B82F6" })
      .setLngLat([hospitalLocation.longitude, hospitalLocation.latitude])
      .setPopup(
        new maplibregl.Popup({ offset: 25 }).setHTML(
          `<div style="padding: 8px;">
            <strong>${hospitalName}</strong>
          </div>`
        )
      )
      .addTo(map.current);

    // Add user location marker if available
    if (userLocation) {
      new maplibregl.Marker({ color: "#10B981" })
        .setLngLat([userLocation.longitude, userLocation.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 25 }).setHTML(
            `<div style="padding: 8px;">
              <strong>Your Location</strong>
            </div>`
          )
        )
        .addTo(map.current);

      // Fit map to show both markers
      const bounds = new maplibregl.LngLatBounds();
      bounds.extend([userLocation.longitude, userLocation.latitude]);
      bounds.extend([hospitalLocation.longitude, hospitalLocation.latitude]);
      
      map.current.fitBounds(bounds, {
        padding: 50,
        maxZoom: 14,
      });

      // Draw line between user and hospital
      map.current.on("load", () => {
        if (!map.current) return;

        map.current.addSource("route", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: [
                [userLocation.longitude, userLocation.latitude],
                [hospitalLocation.longitude, hospitalLocation.latitude],
              ],
            },
          },
        });

        map.current.addLayer({
          id: "route",
          type: "line",
          source: "route",
          layout: {
            "line-join": "round",
            "line-cap": "round",
          },
          paint: {
            "line-color": "#3B82F6",
            "line-width": 3,
            "line-dasharray": [2, 2],
          },
        });
      });
    }

    // Cleanup
    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, [userLocation, hospitalLocation, hospitalName]);

  return <div ref={mapContainer} className="w-full h-full" />;
}
