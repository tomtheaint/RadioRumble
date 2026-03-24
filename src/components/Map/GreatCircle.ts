/**
 * Compute intermediate points along a great circle arc between two coordinates.
 * Handles antimeridian crossing by adjusting longitudes when the path wraps.
 */
export function greatCirclePoints(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
  numPoints: number = 50
): [number, number][] {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const toDeg = (r: number) => (r * 180) / Math.PI;

  const phi1 = toRad(lat1);
  const lambda1 = toRad(lng1);
  const phi2 = toRad(lat2);
  const lambda2 = toRad(lng2);

  // Angular distance between the two points
  const dLambda = lambda2 - lambda1;
  const d = Math.acos(
    Math.sin(phi1) * Math.sin(phi2) +
    Math.cos(phi1) * Math.cos(phi2) * Math.cos(dLambda)
  );

  // If points are essentially the same, return just the two endpoints
  if (d < 1e-10) {
    return [[lat1, lng1], [lat2, lng2]];
  }

  const points: [number, number][] = [];

  for (let i = 0; i <= numPoints; i++) {
    const f = i / numPoints;

    const A = Math.sin((1 - f) * d) / Math.sin(d);
    const B = Math.sin(f * d) / Math.sin(d);

    const x = A * Math.cos(phi1) * Math.cos(lambda1) + B * Math.cos(phi2) * Math.cos(lambda2);
    const y = A * Math.cos(phi1) * Math.sin(lambda1) + B * Math.cos(phi2) * Math.sin(lambda2);
    const z = A * Math.sin(phi1) + B * Math.sin(phi2);

    const lat = toDeg(Math.atan2(z, Math.sqrt(x * x + y * y)));
    let lng = toDeg(Math.atan2(y, x));

    points.push([lat, lng]);
  }

  // Handle antimeridian crossing: split into segments if consecutive points
  // jump more than 180 degrees in longitude. For Leaflet polylines, we adjust
  // longitudes to keep the path continuous rather than splitting.
  for (let i = 1; i < points.length; i++) {
    const diff = points[i][1] - points[i - 1][1];
    if (diff > 180) {
      // Crossed westward past -180
      for (let j = i; j < points.length; j++) {
        points[j][1] -= 360;
      }
    } else if (diff < -180) {
      // Crossed eastward past 180
      for (let j = i; j < points.length; j++) {
        points[j][1] += 360;
      }
    }
  }

  return points;
}
