/**
 * WSJT-X UDP binary protocol decoder.
 *
 * Binary format uses Qt-style serialization:
 *   4-byte big-endian magic (0xADBCCBDA)
 *   4-byte schema version
 *   4-byte message type
 *   Type-specific payload with length-prefixed strings
 *     (4-byte BE length + UTF-8 bytes; length === -1 means null)
 */

const MAGIC = 0xADBCCBDA;

/**
 * Read a Qt-style length-prefixed UTF-8 string from a buffer at the given offset.
 *
 * @param {Buffer} buf
 * @param {number} offset
 * @returns {{value: string|null, nextOffset: number}}
 */
function readQString(buf, offset) {
  if (offset + 4 > buf.length) {
    return { value: null, nextOffset: buf.length };
  }

  const len = buf.readInt32BE(offset);
  offset += 4;

  if (len === -1 || len === 0xFFFFFFFF) {
    return { value: null, nextOffset: offset };
  }

  if (len === 0) {
    return { value: '', nextOffset: offset };
  }

  if (offset + len > buf.length) {
    return { value: null, nextOffset: buf.length };
  }

  const value = buf.toString('utf8', offset, offset + len);
  return { value, nextOffset: offset + len };
}

/**
 * Read a 64-bit unsigned integer as a Number (adequate for frequencies in Hz).
 *
 * @param {Buffer} buf
 * @param {number} offset
 * @returns {{value: number, nextOffset: number}}
 */
function readUint64(buf, offset) {
  if (offset + 8 > buf.length) {
    return { value: 0, nextOffset: buf.length };
  }
  const hi = buf.readUInt32BE(offset);
  const lo = buf.readUInt32BE(offset + 4);
  return { value: hi * 0x100000000 + lo, nextOffset: offset + 8 };
}

/**
 * Decode a Status message (type 2).
 *
 * Layout after header (12 bytes):
 *   QString id
 *   quint64 dialFrequency
 *   QString mode
 *   QString dxCall
 *   QString report
 *   QString txMode
 *   bool txEnabled
 *   bool transmitting
 *   bool decoding
 *   ... (more fields follow but we stop here)
 */
function decodeStatus(buf, offset) {
  const id = readQString(buf, offset);
  offset = id.nextOffset;

  const freq = readUint64(buf, offset);
  offset = freq.nextOffset;

  const mode = readQString(buf, offset);
  offset = mode.nextOffset;

  const dxCall = readQString(buf, offset);
  offset = dxCall.nextOffset;

  const report = readQString(buf, offset);
  offset = report.nextOffset;

  const txMode = readQString(buf, offset);
  offset = txMode.nextOffset;

  let txEnabled = false;
  let transmitting = false;
  let decoding = false;
  if (offset < buf.length) {
    txEnabled = buf.readUInt8(offset) !== 0;
    offset += 1;
  }
  if (offset < buf.length) {
    transmitting = buf.readUInt8(offset) !== 0;
    offset += 1;
  }
  if (offset < buf.length) {
    decoding = buf.readUInt8(offset) !== 0;
    offset += 1;
  }

  return {
    id: id.value,
    frequency: freq.value,
    mode: mode.value,
    dxCall: dxCall.value,
    report: report.value,
    txMode: txMode.value,
    txEnabled,
    transmitting,
    decoding,
  };
}

/**
 * Decode a Logged ADIF message (type 12).
 *
 * Layout after header (12 bytes):
 *   QString id
 *   QString adif
 */
function decodeLoggedAdif(buf, offset) {
  const id = readQString(buf, offset);
  offset = id.nextOffset;

  const adif = readQString(buf, offset);

  return {
    id: id.value,
    adif: adif.value,
  };
}

/**
 * Decode a WSJT-X UDP binary message.
 *
 * @param {Buffer} buffer - Raw UDP packet
 * @returns {{type: number, data: Object}|null} Decoded message or null if malformed
 */
export function decodeWsjtxMessage(buffer) {
  if (!Buffer.isBuffer(buffer) || buffer.length < 12) {
    return null;
  }

  const magic = buffer.readUInt32BE(0);
  if (magic !== MAGIC) {
    return null;
  }

  const schema = buffer.readUInt32BE(4);
  const type = buffer.readUInt32BE(8);
  const payloadOffset = 12;

  try {
    switch (type) {
      case 2:
        return { type, data: decodeStatus(buffer, payloadOffset) };
      case 12:
        return { type, data: decodeLoggedAdif(buffer, payloadOffset) };
      default:
        return { type, data: { raw: buffer.slice(payloadOffset) } };
    }
  } catch {
    return null;
  }
}
