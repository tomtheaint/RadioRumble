import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, Marker, useMapEvents, GeoJSON } from 'react-leaflet';
import L from 'leaflet';
import { useContestStore } from '../../stores/useContestStore';
import { greatCirclePoints } from './GreatCircle';

/** Shape returned by /api/contests/:contestId/map-data (flat array) */
interface RawQso {
  station_callsign: string;
  call: string;
  band: string;
  gridsquare: string;
  my_gridsquare: string;
  coordinates: { lat: number; lng: number } | null;
  stationCoordinates: { lat: number; lng: number } | null;
}

interface StationPos {
  callsign: string;
  pos: { lat: number; lng: number };
}

interface ContactPos {
  callsign: string;
  band: string;
  gridsquare: string;
  pos: { lat: number; lng: number };
  stationPos: { lat: number; lng: number } | null;
}

const DARK_TILES = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const DARK_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>';

const PURPLE = '#512888';
const GOLD = '#F4C55C';

// Center on Kansas (KSU area)
const DEFAULT_CENTER: [number, number] = [39.0, -96.5];
const DEFAULT_ZOOM = typeof window !== 'undefined' && window.innerWidth <= 768 ? 3 : 4;

// GeoJSON CDN URLs
const COUNTRIES_GEOJSON_URL = 'https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json';
const US_STATES_GEOJSON_URL = 'https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json';

// ---------------------------------------------------------------------------
// Country labels (~40 major countries)
// ---------------------------------------------------------------------------
const COUNTRY_LABELS: { name: string; lat: number; lng: number }[] = [
  { name: 'United States', lat: 39.8, lng: -98.5 },
  { name: 'Canada', lat: 56.1, lng: -106.3 },
  { name: 'Mexico', lat: 23.6, lng: -102.5 },
  { name: 'Brazil', lat: -14.2, lng: -51.9 },
  { name: 'Argentina', lat: -38.4, lng: -63.6 },
  { name: 'Colombia', lat: 4.6, lng: -74.1 },
  { name: 'Peru', lat: -9.2, lng: -75.0 },
  { name: 'Chile', lat: -35.7, lng: -71.5 },
  { name: 'Venezuela', lat: 6.4, lng: -66.6 },
  { name: 'United Kingdom', lat: 55.4, lng: -3.4 },
  { name: 'France', lat: 46.6, lng: 1.9 },
  { name: 'Germany', lat: 51.2, lng: 10.4 },
  { name: 'Spain', lat: 40.5, lng: -3.7 },
  { name: 'Italy', lat: 41.9, lng: 12.6 },
  { name: 'Portugal', lat: 39.4, lng: -8.2 },
  { name: 'Netherlands', lat: 52.1, lng: 5.3 },
  { name: 'Poland', lat: 51.9, lng: 19.1 },
  { name: 'Sweden', lat: 60.1, lng: 18.6 },
  { name: 'Norway', lat: 60.5, lng: 8.5 },
  { name: 'Finland', lat: 61.9, lng: 25.7 },
  { name: 'Ukraine', lat: 48.4, lng: 31.2 },
  { name: 'Romania', lat: 45.9, lng: 25.0 },
  { name: 'Turkey', lat: 39.9, lng: 32.9 },
  { name: 'Russia', lat: 61.5, lng: 105.3 },
  { name: 'China', lat: 35.9, lng: 104.2 },
  { name: 'Japan', lat: 36.2, lng: 138.3 },
  { name: 'South Korea', lat: 35.9, lng: 127.8 },
  { name: 'India', lat: 20.6, lng: 79.0 },
  { name: 'Pakistan', lat: 30.4, lng: 69.3 },
  { name: 'Indonesia', lat: -0.8, lng: 113.9 },
  { name: 'Philippines', lat: 12.9, lng: 121.8 },
  { name: 'Thailand', lat: 15.9, lng: 100.9 },
  { name: 'Vietnam', lat: 14.1, lng: 108.3 },
  { name: 'Australia', lat: -25.3, lng: 133.8 },
  { name: 'New Zealand', lat: -40.9, lng: 174.9 },
  { name: 'South Africa', lat: -30.6, lng: 22.9 },
  { name: 'Nigeria', lat: 9.1, lng: 8.7 },
  { name: 'Egypt', lat: 26.8, lng: 30.8 },
  { name: 'Kenya', lat: -0.02, lng: 37.9 },
  { name: 'Saudi Arabia', lat: 23.9, lng: 45.1 },
  { name: 'Iran', lat: 32.4, lng: 53.7 },
];

// ---------------------------------------------------------------------------
// US state labels (all 50 — 2-letter abbreviations with center coords)
// ---------------------------------------------------------------------------
const US_STATE_LABELS: { abbr: string; lat: number; lng: number }[] = [
  { abbr: 'AL', lat: 32.32, lng: -86.90 },
  { abbr: 'AK', lat: 63.59, lng: -154.49 },
  { abbr: 'AZ', lat: 34.05, lng: -111.09 },
  { abbr: 'AR', lat: 35.20, lng: -91.83 },
  { abbr: 'CA', lat: 36.78, lng: -119.42 },
  { abbr: 'CO', lat: 39.55, lng: -105.78 },
  { abbr: 'CT', lat: 41.60, lng: -72.76 },
  { abbr: 'DE', lat: 38.91, lng: -75.53 },
  { abbr: 'FL', lat: 27.66, lng: -81.52 },
  { abbr: 'GA', lat: 32.16, lng: -82.90 },
  { abbr: 'HI', lat: 19.90, lng: -155.58 },
  { abbr: 'ID', lat: 44.07, lng: -114.74 },
  { abbr: 'IL', lat: 40.63, lng: -89.40 },
  { abbr: 'IN', lat: 40.27, lng: -86.13 },
  { abbr: 'IA', lat: 41.88, lng: -93.10 },
  { abbr: 'KS', lat: 39.01, lng: -98.48 },
  { abbr: 'KY', lat: 37.67, lng: -84.67 },
  { abbr: 'LA', lat: 31.17, lng: -91.87 },
  { abbr: 'ME', lat: 45.25, lng: -69.45 },
  { abbr: 'MD', lat: 39.05, lng: -76.64 },
  { abbr: 'MA', lat: 42.41, lng: -71.38 },
  { abbr: 'MI', lat: 44.31, lng: -84.71 },
  { abbr: 'MN', lat: 46.73, lng: -94.69 },
  { abbr: 'MS', lat: 32.35, lng: -89.40 },
  { abbr: 'MO', lat: 38.46, lng: -92.29 },
  { abbr: 'MT', lat: 46.88, lng: -110.36 },
  { abbr: 'NE', lat: 41.49, lng: -99.90 },
  { abbr: 'NV', lat: 38.80, lng: -116.42 },
  { abbr: 'NH', lat: 43.19, lng: -71.57 },
  { abbr: 'NJ', lat: 40.06, lng: -74.41 },
  { abbr: 'NM', lat: 34.52, lng: -105.87 },
  { abbr: 'NY', lat: 43.30, lng: -74.22 },
  { abbr: 'NC', lat: 35.76, lng: -79.02 },
  { abbr: 'ND', lat: 47.55, lng: -101.00 },
  { abbr: 'OH', lat: 40.42, lng: -82.91 },
  { abbr: 'OK', lat: 35.47, lng: -97.09 },
  { abbr: 'OR', lat: 43.80, lng: -120.55 },
  { abbr: 'PA', lat: 41.20, lng: -77.19 },
  { abbr: 'RI', lat: 41.58, lng: -71.48 },
  { abbr: 'SC', lat: 33.84, lng: -81.16 },
  { abbr: 'SD', lat: 43.97, lng: -99.90 },
  { abbr: 'TN', lat: 35.52, lng: -86.58 },
  { abbr: 'TX', lat: 31.97, lng: -99.90 },
  { abbr: 'UT', lat: 39.32, lng: -111.09 },
  { abbr: 'VT', lat: 44.56, lng: -72.58 },
  { abbr: 'VA', lat: 37.43, lng: -78.66 },
  { abbr: 'WA', lat: 47.75, lng: -120.74 },
  { abbr: 'WV', lat: 38.60, lng: -80.45 },
  { abbr: 'WI', lat: 43.78, lng: -88.79 },
  { abbr: 'WY', lat: 43.08, lng: -107.29 },
];

// ---------------------------------------------------------------------------
// Helper: create a text-only divIcon (no pin, no shadow)
// ---------------------------------------------------------------------------
function textIcon(label: string, fontSize: number, opacity: number) {
  return L.divIcon({
    className: '', // no default leaflet styles
    html: `<span style="
      color:#E7DED0;
      opacity:${opacity};
      font-size:${fontSize}px;
      font-family:sans-serif;
      white-space:nowrap;
      pointer-events:none;
      user-select:none;
      text-shadow:0 0 3px rgba(0,0,0,0.7);
    ">${label}</span>`,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}

// ---------------------------------------------------------------------------
// GeoJSON style factories (stable references to avoid re-renders)
// ---------------------------------------------------------------------------
const countryBoundaryStyle: L.PathOptions = {
  color: PURPLE,
  weight: 0.8,
  opacity: 0.3,
  fill: false,
};

const stateBoundaryStyle: L.PathOptions = {
  color: PURPLE,
  weight: 0.5,
  opacity: 0.2,
  fill: false,
};

const countryStyleFn = () => countryBoundaryStyle;
const stateStyleFn = () => stateBoundaryStyle;

// ---------------------------------------------------------------------------
// Sub-component that tracks zoom level and renders labels
// ---------------------------------------------------------------------------
function MapLabels() {
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);

  useMapEvents({
    zoomend: (e) => {
      setZoom(e.target.getZoom());
    },
  });

  // Dynamic font sizes based on zoom
  // Country labels: base 11px at zoom 4 reference
  const countryFontSize = useMemo(
    () => Math.round(11 * (zoom / 4)),
    [zoom]
  );
  // State labels: base 9px at zoom 6 reference
  const stateFontSize = useMemo(
    () => Math.round(9 * (zoom / 6)),
    [zoom]
  );

  // Clamp font sizes to reasonable bounds
  const clampedCountrySize = Math.max(8, Math.min(countryFontSize, 22));
  const clampedStateSize = Math.max(7, Math.min(stateFontSize, 18));

  // Memoize country label icons keyed on zoom
  const countryIcons = useMemo(
    () =>
      COUNTRY_LABELS.map((c) => ({
        ...c,
        icon: textIcon(c.name, clampedCountrySize, 0.4),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [zoom]
  );

  // Memoize state label icons keyed on zoom
  const stateIcons = useMemo(
    () =>
      US_STATE_LABELS.map((s) => ({
        ...s,
        icon: textIcon(s.abbr, clampedStateSize, 0.3),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [zoom]
  );

  // Hide "United States" country label when zoomed in enough to see state labels
  const hideUS = zoom >= 5;

  return (
    <>
      {/* Country labels — always visible (hide US when zoomed in) */}
      {countryIcons
        .filter((c) => !(hideUS && c.name === 'United States'))
        .map((c) => (
          <Marker
            key={`country-${c.name}`}
            position={[c.lat, c.lng]}
            icon={c.icon}
            interactive={false}
            zIndexOffset={-10000}
          />
        ))}

      {/* US state labels — visible at zoom >= 4 */}
      {zoom >= 4 &&
        stateIcons.map((s) => (
          <Marker
            key={`state-${s.abbr}`}
            position={[s.lat, s.lng]}
            icon={s.icon}
            interactive={false}
            zIndexOffset={-10000}
          />
        ))}
    </>
  );
}

export default function QsoMap() {
  const activeContest = useContestStore((s) => s.activeContest);
  const [rawQsos, setRawQsos] = useState<RawQso[]>([]);
  const [loading, setLoading] = useState(true);

  // GeoJSON boundary data
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [countriesGeo, setCountriesGeo] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [statesGeo, setStatesGeo] = useState<any>(null);

  // Fetch GeoJSON boundaries on mount
  useEffect(() => {
    fetch(COUNTRIES_GEOJSON_URL)
      .then((res) => res.json())
      .then((data) => setCountriesGeo(data))
      .catch(() => {});

    fetch(US_STATES_GEOJSON_URL)
      .then((res) => res.json())
      .then((data) => setStatesGeo(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!activeContest) return;

    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/contests/${activeContest.id}/map-data`);
        if (res.ok) {
          const data: RawQso[] = await res.json();
          setRawQsos(data);
        }
      } catch {
        // silently fail
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [activeContest]);

  // Derive unique stations and contacts from the flat QSO array
  const { stationPositions, contactsWithPos } = useMemo(() => {
    const stationMap = new Map<string, StationPos>();
    const contacts: ContactPos[] = [];

    for (const qso of rawQsos) {
      // Collect unique stations by callsign
      if (qso.stationCoordinates && !stationMap.has(qso.station_callsign)) {
        stationMap.set(qso.station_callsign, {
          callsign: qso.station_callsign,
          pos: qso.stationCoordinates,
        });
      }

      // Collect contacts
      if (qso.coordinates) {
        contacts.push({
          callsign: qso.call,
          band: qso.band,
          gridsquare: qso.gridsquare,
          pos: qso.coordinates,
          stationPos: qso.stationCoordinates || null,
        });
      }
    }

    return {
      stationPositions: Array.from(stationMap.values()),
      contactsWithPos: contacts,
    };
  }, [rawQsos]);

  if (!activeContest) {
    return (
      <div style={styles.container}>
        <div style={styles.empty}>Select a contest to view the map.</div>
      </div>
    );
  }

  return (
    <div className="map-container-mobile" style={styles.container}>
      {loading && <div style={styles.loading}>Loading map data...</div>}
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        style={{ width: '100%', height: '100%' }}
        scrollWheelZoom={true}
      >
        <TileLayer url={DARK_TILES} attribution={DARK_ATTR} />

        {/* GeoJSON boundary outlines — rendered BELOW QSO markers */}
        {countriesGeo && (
          <GeoJSON
            key="countries-boundaries"
            data={countriesGeo}
            style={countryStyleFn}
            interactive={false}
          />
        )}
        {statesGeo && (
          <GeoJSON
            key="states-boundaries"
            data={statesGeo}
            style={stateStyleFn}
            interactive={false}
          />
        )}

        {/* Country & state name labels */}
        <MapLabels />

        {/* Great circle paths from station to contacts */}
        {contactsWithPos.map((c, i) => {
          if (!c.stationPos) return null;
          const path = greatCirclePoints(
            c.stationPos.lat,
            c.stationPos.lng,
            c.pos.lat,
            c.pos.lng,
            30
          );
          return (
            <Polyline
              key={`path-${i}`}
              positions={path.map(([lat, lng]) => [lat, lng] as [number, number])}
              pathOptions={{ color: GOLD, weight: 1.5, opacity: 0.4 }}
            />
          );
        })}

        {/* Contact locations: small gold dots */}
        {contactsWithPos.map((c, i) => (
          <CircleMarker
            key={`contact-${i}`}
            center={[c.pos.lat, c.pos.lng]}
            radius={3}
            pathOptions={{ color: GOLD, fillColor: GOLD, fillOpacity: 0.7, weight: 0 }}
          >
            <Tooltip>{c.callsign} ({c.gridsquare}) {c.band}</Tooltip>
          </CircleMarker>
        ))}

        {/* Station locations: purple circles with callsign tooltip */}
        {stationPositions.map((s, i) => (
          <CircleMarker
            key={`station-${i}`}
            center={[s.pos.lat, s.pos.lng]}
            radius={8}
            pathOptions={{
              color: PURPLE,
              fillColor: PURPLE,
              fillOpacity: 0.9,
              weight: 2,
            }}
          >
            <Tooltip permanent direction="top" offset={[0, -10]}>
              {s.callsign}
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: '100%',
    height: '100%',
    position: 'relative',
    background: '#1a1028',
  },
  loading: {
    position: 'absolute',
    top: 12,
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: 1000,
    color: '#E7DED0',
    background: 'rgba(45, 29, 66, 0.9)',
    padding: '6px 16px',
    borderRadius: 6,
    fontSize: 14,
  },
  empty: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    color: '#E7DED0',
    fontSize: 16,
  },
};
