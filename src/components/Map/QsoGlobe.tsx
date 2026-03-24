import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import Globe from 'react-globe.gl';
import type { GlobeInstance } from 'globe.gl';
import { useContestStore } from '../../stores/useContestStore';

interface RawQso {
  station_callsign: string;
  call: string;
  band: string;
  gridsquare: string;
  my_gridsquare: string;
  coordinates: { lat: number; lng: number } | null;
  stationCoordinates: { lat: number; lng: number } | null;
}

interface PointData {
  lat: number;
  lng: number;
  callsign: string;
  band?: string;
  gridsquare?: string;
  type: 'station' | 'contact';
  size: number;
}

interface ArcData {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  callsign: string;
}

interface GeoFeature {
  type: string;
  properties: Record<string, any>;
  geometry: {
    type: string;
    coordinates: any;
  };
}

const PURPLE = '#512888';
const GOLD = '#F4C55C';

interface GlobeLabel {
  lat: number;
  lng: number;
  text: string;
  size: number;
  color: string;
  priority: 1 | 2 | 3 | 4;
  kind: 'country' | 'state';
}

const COUNTRY_LABEL_COLOR = 'rgba(231, 222, 208, 0.5)';
const STATE_LABEL_COLOR = 'rgba(231, 222, 208, 0.3)';

// Priority 1: Large countries visible from far out
// Priority 2: Medium countries visible at mid-zoom
// Priority 3: Small countries visible when closer
const MAJOR_COUNTRIES = new Set([
  'USA', 'CANADA', 'RUSSIA', 'CHINA', 'BRAZIL', 'AUSTRALIA', 'INDIA',
]);

const MEDIUM_COUNTRIES = new Set([
  'UK', 'FRANCE', 'GERMANY', 'JAPAN', 'MEXICO', 'ARGENTINA', 'INDONESIA',
  'SOUTH AFRICA', 'SAUDI ARABIA', 'IRAN', 'EGYPT', 'NIGERIA', 'TURKEY',
  'SPAIN', 'ITALY', 'S. KOREA', 'PAKISTAN', 'COLOMBIA', 'PERU', 'CHILE',
]);

function countryPriority(name: string): 1 | 2 | 3 {
  if (MAJOR_COUNTRIES.has(name)) return 1;
  if (MEDIUM_COUNTRIES.has(name)) return 2;
  return 3;
}

const COUNTRY_LABELS_RAW: Omit<GlobeLabel, 'priority' | 'kind'>[] = [
  { lat: 39.8, lng: -98.5, text: 'USA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 56.1, lng: -106.3, text: 'CANADA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 23.6, lng: -102.5, text: 'MEXICO', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -14.2, lng: -51.9, text: 'BRAZIL', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -38.4, lng: -63.6, text: 'ARGENTINA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -35.7, lng: -71.5, text: 'CHILE', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -9.2, lng: -75.0, text: 'PERU', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 4.6, lng: -74.1, text: 'COLOMBIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 6.4, lng: -66.6, text: 'VENEZUELA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 15.2, lng: -86.2, text: 'HONDURAS', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 21.5, lng: -78.0, text: 'CUBA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 55.4, lng: -3.4, text: 'UK', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 46.6, lng: 1.9, text: 'FRANCE', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 51.2, lng: 10.4, text: 'GERMANY', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 40.5, lng: -3.7, text: 'SPAIN', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 41.9, lng: 12.6, text: 'ITALY', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 39.1, lng: 21.8, text: 'GREECE', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 52.1, lng: 5.3, text: 'NETHERLANDS', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 50.5, lng: 4.5, text: 'BELGIUM', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 46.8, lng: 8.2, text: 'SWITZERLAND', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 47.5, lng: 14.6, text: 'AUSTRIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 52.0, lng: 19.1, text: 'POLAND', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 60.1, lng: 18.6, text: 'SWEDEN', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 61.9, lng: 25.7, text: 'FINLAND', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 62.0, lng: 10.0, text: 'NORWAY', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 56.3, lng: 9.5, text: 'DENMARK', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 38.9, lng: 35.2, text: 'TURKEY', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 48.4, lng: 31.2, text: 'UKRAINE', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 41.7, lng: 44.8, text: 'GEORGIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 61.5, lng: 105.3, text: 'RUSSIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 35.9, lng: 104.2, text: 'CHINA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 36.2, lng: 138.3, text: 'JAPAN', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 35.9, lng: 127.8, text: 'S. KOREA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 20.6, lng: 78.9, text: 'INDIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 30.6, lng: 69.3, text: 'PAKISTAN', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 15.9, lng: 105.8, text: 'THAILAND', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -0.8, lng: 113.9, text: 'INDONESIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 12.9, lng: 121.8, text: 'PHILIPPINES', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -25.3, lng: 133.8, text: 'AUSTRALIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -40.9, lng: 174.9, text: 'NEW ZEALAND', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 23.4, lng: 53.8, text: 'UAE', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 23.9, lng: 45.1, text: 'SAUDI ARABIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 32.4, lng: 53.7, text: 'IRAN', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 26.8, lng: 30.8, text: 'EGYPT', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -1.3, lng: 36.8, text: 'KENYA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -30.6, lng: 22.9, text: 'SOUTH AFRICA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 9.1, lng: 7.5, text: 'NIGERIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 28.4, lng: -9.6, text: 'MOROCCO', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: 7.9, lng: -1.0, text: 'GHANA', size: 0.7, color: COUNTRY_LABEL_COLOR },
  { lat: -6.4, lng: 34.9, text: 'TANZANIA', size: 0.7, color: COUNTRY_LABEL_COLOR },
];

const COUNTRY_LABELS: GlobeLabel[] = COUNTRY_LABELS_RAW.map((c) => ({
  ...c,
  priority: countryPriority(c.text),
  kind: 'country' as const,
}));

const US_STATE_LABELS: GlobeLabel[] = [
  { lat: 32.32, lng: -86.90, text: 'AL', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 63.35, lng: -152.0, text: 'AK', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 34.05, lng: -111.09, text: 'AZ', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 34.97, lng: -92.37, text: 'AR', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 36.78, lng: -119.42, text: 'CA', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 39.55, lng: -105.78, text: 'CO', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 41.60, lng: -72.73, text: 'CT', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 38.91, lng: -75.53, text: 'DE', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 27.66, lng: -81.52, text: 'FL', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 32.16, lng: -82.90, text: 'GA', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 19.90, lng: -155.58, text: 'HI', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 44.07, lng: -114.74, text: 'ID', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 40.63, lng: -89.40, text: 'IL', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 40.27, lng: -86.13, text: 'IN', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 41.88, lng: -93.10, text: 'IA', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 39.01, lng: -98.48, text: 'KS', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 37.84, lng: -84.27, text: 'KY', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 30.98, lng: -91.96, text: 'LA', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 45.25, lng: -69.45, text: 'ME', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 39.05, lng: -76.64, text: 'MD', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 42.41, lng: -71.38, text: 'MA', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 44.31, lng: -85.60, text: 'MI', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 46.73, lng: -94.69, text: 'MN', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 32.35, lng: -89.40, text: 'MS', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 38.46, lng: -92.29, text: 'MO', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 46.88, lng: -110.36, text: 'MT', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 41.49, lng: -99.90, text: 'NE', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 38.80, lng: -116.42, text: 'NV', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 43.19, lng: -71.57, text: 'NH', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 40.06, lng: -74.41, text: 'NJ', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 34.52, lng: -105.87, text: 'NM', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 43.30, lng: -74.22, text: 'NY', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 35.76, lng: -79.02, text: 'NC', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 47.55, lng: -101.00, text: 'ND', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 40.42, lng: -82.91, text: 'OH', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 35.47, lng: -97.52, text: 'OK', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 43.80, lng: -120.55, text: 'OR', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 41.20, lng: -77.19, text: 'PA', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 41.58, lng: -71.48, text: 'RI', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 33.84, lng: -81.16, text: 'SC', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 43.97, lng: -99.90, text: 'SD', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 35.52, lng: -86.15, text: 'TN', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 31.97, lng: -99.90, text: 'TX', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 39.32, lng: -111.09, text: 'UT', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 44.56, lng: -72.58, text: 'VT', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 37.43, lng: -78.66, text: 'VA', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 47.75, lng: -120.74, text: 'WA', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 38.60, lng: -80.45, text: 'WV', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 43.78, lng: -88.79, text: 'WI', size: 0.35, color: STATE_LABEL_COLOR },
  { lat: 43.08, lng: -107.29, text: 'WY', size: 0.35, color: STATE_LABEL_COLOR },
].map((s) => ({ ...s, priority: 4 as const, kind: 'state' as const }));

const ALL_LABELS: GlobeLabel[] = [...COUNTRY_LABELS, ...US_STATE_LABELS];

const COUNTRY_STROKE_COLOR = 'rgba(81, 40, 136, 0.4)';
const STATE_STROKE_COLOR = 'rgba(81, 40, 136, 0.25)';

const COUNTRIES_GEOJSON_URL =
  'https://raw.githubusercontent.com/johan/world.geo.json/master/countries.geo.json';
const US_STATES_GEOJSON_URL =
  'https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json';

/**
 * Determine the max priority level to show at a given altitude.
 *   altitude > 3.0  → only priority 1 (major countries)
 *   1.5 – 3.0       → priority 1–2 (all countries worth showing at mid-zoom)
 *   0.8 – 1.5       → priority 1–3 (all countries + approaching state level)
 *   < 0.8           → priority 1–4 (everything, including US states)
 */
function maxVisiblePriority(altitude: number): number {
  if (altitude > 3.0) return 1;
  if (altitude > 1.5) return 2;
  if (altitude > 0.8) return 3;
  return 4;
}

export default function QsoGlobe() {
  const activeContest = useContestStore((s) => s.activeContest);
  const [rawQsos, setRawQsos] = useState<RawQso[]>([]);
  const [loading, setLoading] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeInstance | undefined>(undefined);

  // Track current zoom altitude for dynamic label filtering/sizing
  const [altitude, setAltitude] = useState(2.2);

  // Boundary polygon features (countries + US states combined)
  const [polygonFeatures, setPolygonFeatures] = useState<GeoFeature[]>([]);

  // Track container size
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const update = () => {
      setDimensions({ width: el.clientWidth, height: el.clientHeight });
    };
    update();

    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fetch GeoJSON boundary data
  useEffect(() => {
    const fetchBoundaries = async () => {
      try {
        const [countriesRes, statesRes] = await Promise.all([
          fetch(COUNTRIES_GEOJSON_URL),
          fetch(US_STATES_GEOJSON_URL),
        ]);

        const combined: GeoFeature[] = [];

        if (countriesRes.ok) {
          const countriesGeo = await countriesRes.json();
          const countryFeatures: GeoFeature[] = (countriesGeo.features || []).map(
            (f: GeoFeature) => ({
              ...f,
              properties: { ...f.properties, _boundaryType: 'country' },
            })
          );
          combined.push(...countryFeatures);
        }

        if (statesRes.ok) {
          const statesGeo = await statesRes.json();
          const stateFeatures: GeoFeature[] = (statesGeo.features || []).map(
            (f: GeoFeature) => ({
              ...f,
              properties: { ...f.properties, _boundaryType: 'state' },
            })
          );
          combined.push(...stateFeatures);
        }

        setPolygonFeatures(combined);
      } catch {
        // silently fail — globe still works without boundaries
      }
    };

    fetchBoundaries();
  }, []);

  // Set initial view when globe mounts and attach camera controls listener
  const handleGlobeReady = useCallback(() => {
    const globe = globeRef.current;
    if (!globe) return;
    globe.pointOfView({ lat: 39, lng: -96.5, altitude: 2.2 }, 1000);

    // Darken the globe material
    const scene = globe.scene();
    if (scene) {
      scene.background = null; // transparent
    }

    // Listen to Three.js camera control changes to track altitude
    try {
      const controls = globe.controls();
      controls.addEventListener('change', () => {
        const pov = globe.pointOfView();
        if (pov && typeof pov.altitude === 'number') {
          setAltitude(pov.altitude);
        }
      });
    } catch {
      // Fallback: poll altitude on an interval if controls() isn't available
      const interval = setInterval(() => {
        try {
          const pov = globe.pointOfView();
          if (pov && typeof pov.altitude === 'number') {
            setAltitude(pov.altitude);
          }
        } catch {
          // ignore
        }
      }, 200);
      // Store cleanup ref — will be cleaned up when component unmounts
      (globe as any).__altitudePollInterval = interval;
    }
  }, []);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      const globe = globeRef.current;
      if (globe && (globe as any).__altitudePollInterval) {
        clearInterval((globe as any).__altitudePollInterval);
      }
    };
  }, []);

  // Fetch QSO data
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

  // Derive points and arcs
  const { points, arcs } = useMemo(() => {
    const stationMap = new Map<string, PointData>();
    const contactPoints: PointData[] = [];
    const arcList: ArcData[] = [];

    for (const qso of rawQsos) {
      if (qso.stationCoordinates && !stationMap.has(qso.station_callsign)) {
        stationMap.set(qso.station_callsign, {
          lat: qso.stationCoordinates.lat,
          lng: qso.stationCoordinates.lng,
          callsign: qso.station_callsign,
          type: 'station',
          size: 0.6,
        });
      }

      if (qso.coordinates) {
        contactPoints.push({
          lat: qso.coordinates.lat,
          lng: qso.coordinates.lng,
          callsign: qso.call,
          band: qso.band,
          gridsquare: qso.gridsquare,
          type: 'contact',
          size: 0.25,
        });

        if (qso.stationCoordinates) {
          arcList.push({
            startLat: qso.stationCoordinates.lat,
            startLng: qso.stationCoordinates.lng,
            endLat: qso.coordinates.lat,
            endLng: qso.coordinates.lng,
            callsign: qso.call,
          });
        }
      }
    }

    return {
      points: [...Array.from(stationMap.values()), ...contactPoints],
      arcs: arcList,
    };
  }, [rawQsos]);

  // Filter and dynamically size labels based on current altitude
  const visibleLabels = useMemo(() => {
    const maxPriority = maxVisiblePriority(altitude);

    return ALL_LABELS
      .filter((label) => label.priority <= maxPriority)
      .map((label) => {
        // Dynamic size: scale inversely with altitude
        let dynamicSize: number;
        if (label.kind === 'country') {
          dynamicSize = Math.max(0.3, Math.min(1.2, 2.0 / altitude));
        } else {
          dynamicSize = Math.max(0.15, Math.min(0.6, 1.0 / altitude));
        }

        return {
          ...label,
          size: dynamicSize,
        };
      });
  }, [altitude]);

  // Polygon stroke color callback — countries vs states
  const getPolygonStrokeColor = useCallback((d: object) => {
    const feature = d as GeoFeature;
    return feature.properties?._boundaryType === 'state'
      ? STATE_STROKE_COLOR
      : COUNTRY_STROKE_COLOR;
  }, []);

  if (!activeContest) {
    return (
      <div style={styles.container}>
        <div style={styles.empty}>Select a contest to view the globe.</div>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={styles.container}>
      {loading && <div style={styles.loading}>Loading globe data...</div>}
      {dimensions.width > 0 && dimensions.height > 0 && (
        <Globe
          ref={globeRef as any}
          width={dimensions.width}
          height={dimensions.height}
          globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
          backgroundImageUrl=""
          backgroundColor="rgba(0,0,0,0)"
          atmosphereColor={PURPLE}
          atmosphereAltitude={0.18}
          onGlobeReady={handleGlobeReady}
          // Points
          pointsData={points}
          pointLat="lat"
          pointLng="lng"
          pointAltitude={0.01}
          pointRadius="size"
          pointColor={(d: any) => (d as PointData).type === 'station' ? PURPLE : GOLD}
          pointLabel={(d: any) => {
            const p = d as PointData;
            if (p.type === 'station') {
              return `<div style="background:rgba(45,29,66,0.92);color:#E7DED0;padding:4px 10px;border-radius:4px;font-size:13px;border:1px solid ${PURPLE}"><b>${p.callsign}</b> (Station)</div>`;
            }
            return `<div style="background:rgba(45,29,66,0.92);color:#E7DED0;padding:4px 10px;border-radius:4px;font-size:13px;border:1px solid ${GOLD}"><b>${p.callsign}</b><br/>${p.gridsquare || ''} ${p.band || ''}</div>`;
          }}
          // Arcs
          arcsData={arcs}
          arcStartLat="startLat"
          arcStartLng="startLng"
          arcEndLat="endLat"
          arcEndLng="endLng"
          arcColor={() => [`${GOLD}66`, `${GOLD}CC`]}
          arcAltitude={0.2}
          arcStroke={0.6}
          arcDashLength={0.6}
          arcDashGap={0.3}
          arcDashAnimateTime={1500}
          arcLabel={(d: any) => {
            const a = d as ArcData;
            return `<div style="background:rgba(45,29,66,0.92);color:#E7DED0;padding:4px 10px;border-radius:4px;font-size:13px;border:1px solid ${GOLD}">${a.callsign}</div>`;
          }}
          // Boundary polygons (countries + US states)
          polygonsData={polygonFeatures}
          polygonCapColor={() => 'rgba(0,0,0,0)'}
          polygonSideColor={() => 'rgba(0,0,0,0)'}
          polygonStrokeColor={getPolygonStrokeColor}
          polygonAltitude={0.005}
          polygonsTransitionDuration={0}
          // Labels — dynamically filtered and sized based on zoom altitude
          labelsData={visibleLabels}
          labelLat="lat"
          labelLng="lng"
          labelText="text"
          labelSize="size"
          labelColor="color"
          labelResolution={2}
          labelAltitude={0.01}
          labelDotRadius={0}
        />
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: '100%',
    height: '100%',
    position: 'relative',
    background: '#1a1028',
    overflow: 'hidden',
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
