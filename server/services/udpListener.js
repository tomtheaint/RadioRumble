/**
 * UDP listener for WSJT-X packets.
 */

import dgram from 'node:dgram';
import { decodeWsjtxMessage } from './wsjtxDecoder.js';

/**
 * Start a UDP listener that decodes WSJT-X messages.
 *
 * @param {number} port - UDP port to bind (WSJT-X default: 2237)
 * @param {(message: {type: number, data: Object}, rinfo: Object) => void} onMessage - Callback for decoded messages
 * @returns {dgram.Socket} The bound UDP socket
 */
export function startUdpListener(port, onMessage) {
  const socket = dgram.createSocket('udp4');

  socket.on('message', (buf, rinfo) => {
    const decoded = decodeWsjtxMessage(buf);
    if (decoded) {
      console.log(
        `[UDP] type=${decoded.type} from ${rinfo.address}:${rinfo.port} (${buf.length} bytes)`
      );
      onMessage(decoded, rinfo);
    }
  });

  socket.on('listening', () => {
    const addr = socket.address();
    console.log(`[UDP] Listening on ${addr.address}:${addr.port}`);
  });

  socket.on('error', (err) => {
    console.error(`[UDP] Socket error: ${err.message}`);
    socket.close();
  });

  socket.bind(port);

  return socket;
}
