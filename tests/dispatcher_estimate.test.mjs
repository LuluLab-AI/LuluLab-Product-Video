import test from 'node:test';
import assert from 'node:assert/strict';
import { estimate, buildPlan, estimateItems } from '../scripts/dispatcher_commerce.mjs';
const media = { url: 'https://assets.example/product.png', mimeType: 'image/png' };
const configs = [1, 10, 11, 20].map(count => ({ kind: 'video', productImages: [media], duration: 35, count }));

test('estimate returns server pricing without quotes or task submission', async () => {
  for (const config of configs) {
    const calls = [];
    const response = { credits: 123, version: 'test-rates', breakdown: [{ credits: 123 }] };
    const client = { async request(path, options) { calls.push({ path, ...options }); return response; } };
    assert.deepEqual(await estimate(config, client), response);
    assert.deepEqual(calls, [{ path: '/billing/estimates', method: 'POST', body: { items: estimateItems(buildPlan(config)) } }]);
  }
});

test('unavailable or invalid pricing never falls through to task submission', async () => {
  for (const credits of [undefined, null, '123', -1, NaN, Infinity, 1.5]) {
    const calls = [];
    await assert.rejects(estimate(configs[0], { async request(path) { calls.push(path); return { credits }; } }), /valid credit total/);
    assert.deepEqual(calls, ['/billing/estimates']);
  }
  await assert.rejects(estimate(configs[0], { async request() { throw Error('pricing unavailable'); } }), /pricing unavailable/);
  assert.equal((await estimate(configs[0], { async request() { return { credits: 0 }; } })).credits, 0);
});

test('batch estimate counts all videos once and one planning task', () => {
  for (const config of configs) {
    const items = estimateItems(buildPlan(config));
    assert.deepEqual(items[0], { workflowId: 'SalesVideoPromptV3' });
    assert.equal(items.slice(1).reduce((sum, item) => sum + item.input.videoCount, 0), config.count);
    for (const item of items.slice(1)) {
      assert.equal(item.workflowId, 'VideoCreationV1');
      assert.equal(item.input.duration, 35);
      assert.equal(item.input.model, 'seedance-2-fast');
      assert.equal(item.input.resolution, '720p');
      assert.ok(item.input.videoCount <= 10);
    }
  }
});
