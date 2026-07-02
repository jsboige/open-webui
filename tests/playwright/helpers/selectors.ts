/**
 * Centralized CSS selectors for Open WebUI E2E tests.
 * Based on actual OWUI v0.8.7 accessibility tree.
 *
 * NOTE: OWUI uses localized aria-labels (French when locale=fr-FR).
 * Use language-independent selectors (roles, IDs) where possible.
 * For localized labels, use regex patterns via page.getByRole() in test code.
 */

// --- Authentication ---
export const AUTH = {
  emailInput: 'input[autocomplete="email"]',
  passwordInput: 'input[type="password"]',
  submitButton: 'button[type="submit"]',
  authPage: '#auth-page',
} as const;

// --- Navigation ---
export const NAV = {
  chatSearch: '#chat-search',
  newChatButton: '#new-chat-button',
  chatContextMenu: '#chat-context-menu-button',
} as const;

// --- Model Selection ---
export const MODEL = {
  // v0.10: the aria-label is localized ("Modèle sélectionné : X" in fr-FR),
  // so the old `button[aria-label^="Select"]` no longer matches. Prefer the
  // stable id, keep aria-label variants as fallback for older versions.
  selectorButton:
    'button[id^="model-selector-"], button[aria-label^="Select" i], button[aria-label^="Modèle" i], button[aria-label^="Sélection" i]',
  // v0.10: listbox aria-label is localized ("Modèles disponibles" in fr) and
  // it is the only listbox shown while the dropdown is open — match on role.
  modelListbox: '[role="listbox"]',
  modelOption: '[role="option"]',
  // Search field of the dropdown (v0.10: stable id, placeholder fallbacks)
  searchInput:
    '#model-search-input, [role="listbox"] input, input[placeholder*="odel" i], input[placeholder*="odèle" i]',
  addModelButton: 'button[aria-label="Add Model"]',
} as const;

// --- Chat ---
export const CHAT = {
  input: '#chat-input',
  inputContainer: '#chat-input-container',
  submitButton: '#chat-input-container button[type="submit"]',
  userMessage: '.chat-user',
  assistantMessage: '.chat-assistant',
  // v0.8.7: "Generation Info" no longer exists, use status toggle button instead
  statusToggle: 'button[aria-label="Toggle status history"]',
  // Action buttons are localized — use role-based selectors in code
  // FR: "Regénérer", EN: "Regenerate"
  // FR: "Copier", EN: "Copy"
  // FR: "Modifier", EN: "Edit"
  saveEditButton: '#save-edit-message-button',
  closeEditButton: '#close-edit-message-button',
  confirmEditButton: '#confirm-edit-message-button',
  availableTools: 'button[aria-label="Available Tools"]',
} as const;

// --- Share ---
export const SHARE = {
  shareButton: '#chat-share-button',
  copyAndShareButton: '#copy-and-share-chat-button',
} as const;

// --- Sidebar ---
export const SIDEBAR = {
  searchContainer: '#search-container',
} as const;

// --- Account / user menu ---
// Verified against v0.10.2 fr-FR: the avatar button (bottom of sidebar)
// carries the localized aria-label "Menu utilisateur" and has no stable id.
// Menu entries are <button>s targeted by label via getByRole('button', { name }).
export const ACCOUNT = {
  menuButton:
    'button[aria-label="Menu utilisateur"], button[aria-label="User menu" i]',
  // v0.10.2 fr calls the settings entry "Réglages" (not "Paramètres")
  settingsEntry: /r[ée]glages|param[èe]tres|settings/i,
  logout: /d[ée]connexion|log ?out|sign ?out/i,
  archivedChats: /conversations archiv[ée]es|archived chats/i,
} as const;
