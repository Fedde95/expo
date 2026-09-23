/**
 * Copyright © 2022 650 Industries.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { buildUrlForBundle } from './buildUrlForBundle';
import { loadBundleAsync } from './loadBundle';

/**
 * Must satisfy the requirements of the Metro bundler.
 * https://github.com/react-native-community/discussions-and-proposals/blob/main/proposals/0605-lazy-bundling.md#__loadbundleasync-in-metro
 */
type AsyncRequire = ((path: string | readonly string[]) => Promise<void>) & {
  isReady?: (paths: readonly string[]) => boolean;
};

/** Create an `loadBundleAsync` function in the expected shape for Metro bundler. */
export function buildAsyncRequire(): AsyncRequire {
  const cache = new Map<string, Promise<void>>();
  const runtime = globalThis as typeof globalThis & Record<string, unknown>;
  // Footers may run before installation. Reuse the live, prefix-scoped registry.
  const registryKey = `${runtime.__METRO_GLOBAL_PREFIX__ ?? ''}__expo_chunk_completion__`;
  const ready =
    process.env.EXPO_OS === 'web' && process.env.NODE_ENV === 'production'
      ? ((runtime[registryKey] ??= new Set<string>()) as Set<string>)
      : undefined;
  const requestKey = (path: string): string => {
    if (!ready) return path;
    const url = buildUrlForBundle(path);
    return typeof document === 'undefined' ? url : new URL(url, document.baseURI).href;
  };

  async function loadFile(path: string): Promise<void> {
    const key = requestKey(path);
    if (ready?.has(key)) return;
    if (cache.has(key)) {
      return cache.get(key)!;
    }

    const promise = loadBundleAsync(path).then(
      () => {
        ready?.add(key);
      },
      (error) => {
        cache.delete(key);
        throw error;
      }
    );

    cache.set(key, promise);

    return promise;
  }

  const load: AsyncRequire = async function universal_loadBundleAsync(path): Promise<void> {
    if (typeof path === 'string') return loadFile(path);
    // Files register factories; execution happens only after every prerequisite loads.
    // Cache individual files so overlapping imports and scalar requests share work.
    await Promise.all(path.map(loadFile));
  };
  if (ready) load.isReady = (paths) => paths.every((path) => ready.has(requestKey(path)));
  return load;
}
