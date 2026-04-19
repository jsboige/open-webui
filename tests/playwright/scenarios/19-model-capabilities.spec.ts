import { test, expect } from '@playwright/test';
import { getTenantConfig } from '../fixtures/tenant';
import {
  apiLogin,
  chatCompletionFull,
  chatCompletionWithImage,
  chatCompletionWithTools,
} from '../helpers/api';

// 128x128 red square on white background. 16x16 was rejected by local vLLM
// vision models ("broken data stream"); 128x128 is the smallest size that
// every tested backend (vLLM Qwen3.6, OmniCoder, Claude Haiku, GLM-4.7)
// accepts. PNG is only ~380 bytes so the base64 stays inline-friendly.
const RED_SQUARE_B64 =
  'iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAIAAABMXPacAAABQ0lEQVR4nO3ZsQnAMAwAwThk/5WVGVyYg+SvFxY8qrxm5opzw7dTAK8LwAqAFQArAFYArABYAbACYAXACoAVACsAVgDs2Z5Y68giX7LzxdIFYAXACoAVACsAVgCsAFgBsAJgBcAKgBUAKwBWAKwAWAGwAmAFwAqAFQArAFYArABYAbACYAXACoAVACsAVgCsAFgBsAJgBcAKgBUAKwBWAKwAWAGwAmAFwAqAFQArAFYArABYAbACYAXACoAVACsAVgCsAFgBsAJgBcAKgBUAKwBWAKwAWAGwAmAFwAqAFQArAFYArABYAbACYAXACoAVACsAVgCsAFgBsAJgBcAKgBUAKwBWAKwAWAGwAmAFwAqAFQArAFYArABYAbBne2LmyCJ/1QVgBcAKgBUAKwBWAKwAWAGwAmAFwAqAFQArAFaAy3oBuDUH/wA0a9sAAAAASUVORK5CYII=';

/**
 * Scenario 19 — Model Capabilities (myia only)
 *
 * Verifies declared capabilities of wrappers actually work end-to-end:
 *   19.1 Vision: send an image, expect a non-trivial response
 *   19.2 Function calling: prompt requiring a tool, expect a tool_call
 *   19.3 Thinking mode: Qwen_think* emits <think> tags, *-fast / instruct does not
 *
 * Run: npx playwright test scenarios/19-model-capabilities.spec.ts --project=myia
 */

// Vision-capable models to verify (per OWUI wrapper capabilities.vision=true or
// provider docs for external ones). Local.omnicoder-9b, Local.qwen3.6-35b-a3b,
// z-ai/glm-4.7, and anthropic/claude-haiku-4.5 all declare vision support.
const VISION_MODELS = [
  { id: 'Local.qwen3.6-35b-a3b', name: 'Qwen3.6-35B' },
  { id: 'Local.omnicoder-9b', name: 'OmniCoder-9B' },
  { id: 'vision-expert', name: 'vision-expert wrapper' },
  { id: 'OpenRouter.z-ai/glm-4.7', name: 'GLM-4.7 (OpenRouter)' },
  { id: 'OpenRouter.anthropic/claude-haiku-4.5', name: 'Claude Haiku 4.5' },
];

// Models that must support OpenAI-style function calling. Local wrappers need
// `function_calling: native` in their params — the Fast wrapper is general chat,
// so it is intentionally NOT tested here.
const TOOL_MODELS = [
  { id: 'MistralAI.devstral-small-latest', name: 'Devstral Small' },
  { id: 'OpenRouter.anthropic/claude-haiku-4.5', name: 'Claude Haiku 4.5' },
];

const WEATHER_TOOL = {
  type: 'function',
  function: {
    name: 'get_weather',
    description: 'Get the current weather for a given city',
    parameters: {
      type: 'object',
      properties: {
        city: { type: 'string', description: 'City name' },
      },
      required: ['city'],
    },
  },
};

test.describe('19 — Model Capabilities (myia)', () => {
  let token = '';
  let baseUrl = '';

  test.beforeAll(async ({ request }) => {
    const config = getTenantConfig('myia');
    baseUrl = config.url;
    token = await apiLogin(request, baseUrl, config.email, config.password);
  });

  // ─── 19.1 Vision ──────────────────────────────────────────────

  test.describe('19.1 — Vision', () => {
    const imageBase64 = RED_SQUARE_B64;

    // Fixed in this branch by patching the detoxify filter pipeline to extract
    // text from multi-part OpenAI content (see pipelines/detoxify_filter_pipeline.py).
    // The upstream detoxify filter crashed on list-typed `content`, returning 500
    // to OWUI which silently swallowed it to `null`. Patch is shared across all
    // 7 tenants via the `pipelines` alias on the open-webui-shared network.
    for (const { id, name } of VISION_MODELS) {
      test(`${name} accepts image input`, async ({ request }) => {
        const response = await chatCompletionWithImage(
          request,
          baseUrl,
          token,
          id,
          'What shape and color do you see? Reply in one short sentence.',
          imageBase64,
          { timeout: 180_000, maxTokens: 200 },
        );
        expect(response, `${name}: response should not be null (HTTP OK + choice content)`)
          .not.toBeNull();
        expect(response!.length, `${name}: response should be non-trivial`).toBeGreaterThan(10);
      });
    }
  });

  // ─── 19.2 Function calling ────────────────────────────────────

  test.describe('19.2 — Function Calling', () => {
    for (const { id, name } of TOOL_MODELS) {
      test(`${name} emits a tool_call when asked about weather`, async ({ request }) => {
        const toolCalls = await chatCompletionWithTools(
          request,
          baseUrl,
          token,
          id,
          'What is the current weather in Paris? Use the tool if you need to.',
          [WEATHER_TOOL],
          { timeout: 60_000 },
        );
        expect(toolCalls, `${name}: expected tool_calls in response`).not.toBeNull();
        expect(toolCalls!.length, `${name}: at least one tool call`).toBeGreaterThan(0);
        const called = toolCalls![0].function?.name;
        expect(called, `${name}: should call get_weather (got ${called})`).toBe('get_weather');
      });
    }
  });

  // ─── 19.3 Thinking mode ───────────────────────────────────────

  test.describe('19.3 — Thinking Mode', () => {
    const THINKING_ON = ['Qwen_think', 'Qwen_think-code', 'Qwen_think-reason'];
    const THINKING_OFF = ['Qwen_instruct', 'Local.qwen3.6-35b-a3b-fast'];

    for (const id of THINKING_ON) {
      test(`${id} produces reasoning`, async ({ request }) => {
        const msg = await chatCompletionFull(
          request,
          baseUrl,
          token,
          id,
          'Briefly: what is 17 * 23? Show your reasoning.',
          { timeout: 120_000 },
        );
        expect(msg, `${id}: response not null`).not.toBeNull();
        // OWUI extracts <think>...</think> blocks into a separate `reasoning`
        // field on the assistant message. Accept either non-empty reasoning OR
        // inline <think> tags in content (older models).
        const hasReasoning = (msg!.reasoning?.length ?? 0) > 30;
        const hasInlineThink = /<think>/.test(msg!.content ?? '');
        expect(
          hasReasoning || hasInlineThink,
          `${id}: expected reasoning field or <think> tags (content=${(msg!.content ?? '').slice(0, 60)})`,
        ).toBe(true);
      });
    }

    for (const id of THINKING_OFF) {
      test(`${id} has no reasoning`, async ({ request }) => {
        const msg = await chatCompletionFull(
          request,
          baseUrl,
          token,
          id,
          'What is 2+2? Just the number.',
          { timeout: 60_000 },
        );
        expect(msg, `${id}: response not null`).not.toBeNull();
        const hasReasoning = (msg!.reasoning?.length ?? 0) > 30;
        const hasInlineThink = /<think>/.test(msg!.content ?? '');
        expect(
          hasReasoning || hasInlineThink,
          `${id}: must not produce reasoning or <think> tags`,
        ).toBe(false);
      });
    }
  });
});
