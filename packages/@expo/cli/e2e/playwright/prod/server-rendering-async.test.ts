import { test, expect } from '@playwright/test';

import { clearEnv, restoreEnv } from '../../__tests__/export/export-side-effects';
import { getRouterE2ERoot } from '../../__tests__/utils';
import { createExpoServe, executeExpoAsync } from '../../utils/expo';
import { pageCollectErrors } from '../page';

test.beforeAll(() => clearEnv());
test.afterAll(() => restoreEnv());

const projectRoot = getRouterE2ERoot();
test.describe.configure({ mode: 'serial' });

for (const strategy of ['legacy', 'bitset'] as const) {
  const outputDir = `dist-server-rendering-async-playwright-${strategy}`;
  test.describe(`server rendering with async routes in production (${strategy})`, () => {
    const expoServe = createExpoServe({
      cwd: projectRoot,
      env: {
        NODE_ENV: 'production',
        TEST_SECRET_KEY: 'test-secret-key',
      },
    });

    test.beforeAll(async () => {
      console.time('expo export');
      await executeExpoAsync(projectRoot, ['export', '-p', 'web', '--output-dir', outputDir], {
        env: {
          NODE_ENV: 'production',
          EXPO_USE_STATIC: 'server',
          E2E_ROUTER_SRC: strategy === 'bitset' ? 'static-rendering-bitset' : 'static-rendering',
          E2E_ROUTER_ASYNC: 'true',
        },
      });
      console.timeEnd('expo export');

      console.time('expo serve');
      await expoServe.startAsync([outputDir]);
      console.timeEnd('expo serve');
    });
    test.afterAll(async () => {
      await expoServe.stopAsync();
    });

    test('loads page without JavaScript errors', async ({ page }) => {
      const pageErrors = pageCollectErrors(page);
      const scripts: string[] = [];
      page.on('request', (request) => {
        if (request.resourceType() === 'script') scripts.push(request.url());
      });

      await page.goto(expoServe.url.href);
      await page.waitForSelector('[data-testid="index-text"]');

      expect(pageErrors.errors).toEqual([]);
      if (strategy === 'bitset') {
        const ready = await page.evaluate(() => {
          const runtime = globalThis as any;
          const urls = [...runtime.__expo_chunk_completion__] as string[];
          return { urls, ready: runtime.__loadBundleAsync.isReady(urls) };
        });
        expect(ready.urls.length).toBeGreaterThan(0);
        expect(ready.ready).toBe(true);
        expect(new Set(scripts).size).toBe(scripts.length);
        expect(pageErrors.logs.filter((log) => /hydration/i.test(log.text()))).toEqual([]);
      }
    });

    if (strategy === 'bitset') {
      test('waits for shared registrations when the target factory is already present', async ({
        page,
      }) => {
        const errors = pageCollectErrors(page);
        await page.goto(new URL('/links', expoServe.url).href);
        await expect(page.getByTestId('links-one')).toBeVisible();
        const html = await (await page.request.get(new URL('/about', expoServe.url).href)).text();
        const urls = [...html.matchAll(/<script[^>]*src="([^"]+)"/g)].map(
          (match) => new URL(match[1]!, expoServe.url).href
        );
        const target = urls.find((url) => /\/about-[^/]+\.js$/.test(url))!;
        expect(target).toBeTruthy();
        // Register the route first, without evaluating its factory or loading its shared file.
        await page.addScriptTag({ url: target });
        const missing = await page.evaluate(
          (urls) =>
            urls.filter(
              (url) =>
                url.includes('/__shared-') && !(globalThis as any).__loadBundleAsync.isReady([url])
            ),
          urls
        );
        expect(missing.length).toBeGreaterThan(0);
        let release!: () => void;
        let requested!: () => void;
        const blocked = new Promise<void>((resolve) => {
          release = resolve;
        });
        const requestStarted = new Promise<void>((resolve) => {
          requested = resolve;
        });
        await page.route(missing[0]!, async (route) => {
          requested();
          await blocked;
          await route.continue();
        });
        try {
          await page.getByTestId('links-one').click();
          await requestStarted;
          expect(errors.errors).toEqual([]);
        } finally {
          release();
        }
        await expect(page.getByTestId('content')).toHaveText('About');
        expect(errors.errors).toEqual([]);
      });
    }
  });
}
