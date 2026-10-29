import { type Locator, type Page } from '@playwright/test';

/**
 * Role-agnostic locators for the menus of the chat composer and the user menu.
 *
 * Open WebUI v0.12.5 migrated those popovers to real ARIA menu semantics:
 * entries that used to render as `<button>` are now `<menuitem>`, and the
 * per-tool checkboxes are now `<menuitemcheckbox>`. Measured on 2026-10-29
 * with the students' E2E suite (groupe-owui-qa) running against v0.12.5:
 *   - "Joindre une connaissance"      menuitem   (was button)
 *   - "Outils N"                       menuitem   (was button)
 *   - tool row (e.g. "F1 QA Tool …")   menuitemcheckbox (was button)
 * The features are intact — only the accessible role changed. A locator bound
 * to a single role silently stops matching, which is how a version bump
 * turns into a red suite with no product bug behind it.
 *
 * These helpers match the old and the new roles, so the same suite runs on
 * v0.11.x and v0.12.x without a per-version branch.
 */
export function menuEntry(page: Page, name: string | RegExp): Locator {
  return page
    .getByRole('menuitem', { name })
    .or(page.getByRole('menuitemcheckbox', { name }))
    .or(page.getByRole('button', { name }))
    .first();
}

/** Same as {@link menuEntry} for a row that carries a checked/pressed state. */
export function menuCheckbox(page: Page, name: string | RegExp): Locator {
  return page
    .getByRole('menuitemcheckbox', { name })
    .or(page.getByRole('menuitem', { name }))
    .or(page.getByRole('button', { name }))
    .first();
}

/**
 * Reads the "selected" state of a menu row across versions: v0.12.5 exposes
 * `aria-checked` on the new `menuitemcheckbox` role, older builds used
 * `aria-pressed` on a plain button.
 */
export async function menuItemState(locator: Locator): Promise<string | null> {
  return (
    (await locator.getAttribute('aria-checked')) ??
    (await locator.getAttribute('aria-pressed'))
  );
}
