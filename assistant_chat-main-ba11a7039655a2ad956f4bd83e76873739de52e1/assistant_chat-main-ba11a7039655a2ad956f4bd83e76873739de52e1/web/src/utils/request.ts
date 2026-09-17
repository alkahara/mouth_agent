/**
 * Axios request wrapper with authentication
 */

import axios, { type AxiosInstance, type AxiosError } from "axios";
import { getToken, removeToken } from "./auth";
import router from "../router";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const request: AxiosInstance = axios.create({
  baseURL: apiBaseUrl,
  timeout: 60000,
});

// Request interceptor - add token to headers
request.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // Log outgoing request for debugging payload issues.
    const method = config.method ? config.method.toUpperCase() : "GET";
    // axios may store data as JSON string or object; log as-is.
    // eslint-disable-next-line no-console
    console.log("[request]", method, config.url, { data: config.data, params: config.params });
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle 401 errors
request.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      removeToken();
      router.push("/login");
    }
    return Promise.reject(error);
  }
);

export default request;
