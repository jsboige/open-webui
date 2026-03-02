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
  // Matches both "Select a model" (empty) and "Selected model: X" (with default)
  selectorButton: 'button[aria-label^="Select"]',
  // Model items in dropdown are <option> role elements inside a listbox
  modelListbox: '[role="listbox"][aria-label="Available models"]',
  modelOption: '[role="option"]',
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
