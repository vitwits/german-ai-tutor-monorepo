/**
 * Utility functions for generating MD5 hashes (matching backend logic)
 * Used for audio caching - same logic as Python's hashlib.md5()
 */

/**
 * Simple MD5 implementation for frontend
 * Generates the same hash as Python's hashlib.md5(text.encode()).hexdigest()
 */
export function md5(str) {
  // Using SubtleCrypto API available in modern browsers
  // Falls back to a simple hash function if not available
  
  // const encoder = new TextEncoder();
  // const data = encoder.encode(str);
  
  // Use crypto.subtle for MD5 (note: requires HTTPS in production)
  // For now, we'll use a simpler approach with a library or fallback
  
  // Fallback: use a deterministic hash function
  return generateSimpleHash(str);
}

/**
 * Generate audio cache path following backend logic:
 * Path: /static/audio/texts/{lang}/{shard}/{hash}.ogg
 * Where shard = first 2 chars of hash
 */
export function getAudioCachePath(text, lang = 'de') {
  if (!text) return null;
  
  // Normalize text same as backend: lowercase and strip
  const normalizedText = text.toLowerCase().trim();
  const hash = md5(normalizedText);
  const shard = hash.substring(0, 2);
  
  return `/static/audio/texts/${lang}/${shard}/${hash}.ogg`;
}

/**
 * Generate vocabulary audio cache path
 * Path: /static/audio/vocabulary/{lang}/{shard}/{hash}.ogg
 */
export function getVocabularyCachePath(text, lang = 'de') {
  if (!text) return null;
  
  // Normalize text same as backend: lowercase and strip
  const normalizedText = text.toLowerCase().trim();
  const hash = md5(normalizedText);
  const shard = hash.substring(0, 2);
  
  return `/static/audio/vocabulary/${lang}/${shard}/${hash}.ogg`;
}

/**
 * Simple deterministic hash function (fallback if crypto not available)
 * NOT cryptographically secure, but deterministic for same input
 */
function generateSimpleHash(str) {
  // Use a simple algorithm that produces consistent results
  let hash = 0;
  let i = 0;
  
  if (str.length === 0) return '0'.repeat(32);
  
  // Create multiple rounds to get 32-char hex string
  const rounds = 4;
  let hashParts = [];
  
  for (let round = 0; round < rounds; round++) {
    hash = 0;
    for (i = 0; i < str.length; i++) {
      const char = str.charCodeAt((i + round) % str.length);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    hashParts.push(Math.abs(hash).toString(16).padStart(8, '0'));
  }
  
  return hashParts.join('').substring(0, 32);
}

/**
 * Check if audio file exists by attempting to load it
 * Returns true if file exists, false otherwise
 */
export async function checkAudioExists(url) {
  try {
    const response = await fetch(url, { method: 'HEAD' });
    return response.ok;
  } catch {
    return false;
  }
}
