import { writable, get } from 'svelte/store';
import { apiLogin, apiLogin2fa } from '../providers/api';
import { websocket } from '../providers/websocket';
import { default as currentUserStore } from './current-user';

export const isAuthenticated = writable(false);
export const loginModal = writable(null);
export const credentials = writable(null);

export const showLogin = () => {
  // Show modal
  get(loginModal).show();
};

const finalizeLogin = (username) => {
  currentUserStore.set(username);
  credentials.set(null);
  try {
    websocket.set({ type: 'client_init', auth: '' });
  } catch (e) {
    /* empty */
  }
  setTimeout(function () {
    isAuthenticated.set(true);
  }, 1000);
};

export const doLogin = async (username, password) => {
  const login = await apiLogin(username, password);

  if (!login || !login.success) {
    return login;
  }

  if (login.requires_2fa) {
    return login;
  }

  finalizeLogin(username);
  return login;
};

export const doLogin2fa = async (username, totp_code, preauth_token) => {
  const result = await apiLogin2fa(username, totp_code, preauth_token);

  if (result && result.success) {
    finalizeLogin(username);
  }

  return result;
};

export const doLogout = () => {
  // Delete all cookies....
  document.cookie.split(';').forEach(function (c) {
    document.cookie = c.trim().split('=')[0] + '=;' + 'expires=Thu, 01 Jan 1970 00:00:00 UTC;';
  });

  websocket.set({ type: 'client_init', auth: '' });
  credentials.set({});
  currentUserStore.set(null);

  setTimeout(function () {
    isAuthenticated.set(false);
  }, 500);
};
