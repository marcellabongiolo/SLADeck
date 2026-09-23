const ACCESS_TOKEN_KEY="sladeck_access_token";
const REFRESH_TOKEN_KEY="sladeck_refresh_token";
export function saveSession(accessToken:string,refreshToken:string){if(typeof window==="undefined")return;localStorage.setItem(ACCESS_TOKEN_KEY,accessToken);localStorage.setItem(REFRESH_TOKEN_KEY,refreshToken)}
export function getAccessToken(){if(typeof window==="undefined")return null;return localStorage.getItem(ACCESS_TOKEN_KEY)}
export function clearSession(){if(typeof window==="undefined")return;localStorage.removeItem(ACCESS_TOKEN_KEY);localStorage.removeItem(REFRESH_TOKEN_KEY)}
