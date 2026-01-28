import { useState, useCallback, useRef, useEffect } from "react";
import {
  Settings as SettingsIcon,
  Upload,
  Link,
  RefreshCw,
  CheckCircle,
  XCircle,
  FileArchive,
  AlertCircle,
} from "lucide-react";
import {
  uploadExport,
  getAuthStatus,
  getAuthUrl,
  triggerSync,
} from "../api/client";
import type { AuthStatus, SyncResult } from "../api/client";

export default function Settings() {
  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auth state
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  // Sync state
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  // Fetch auth status on mount
  useEffect(() => {
    fetchAuthStatus();
  }, []);

  const fetchAuthStatus = async () => {
    try {
      const status = await getAuthStatus();
      setAuthStatus(status);
      setAuthError(null);
    } catch {
      setAuthError("Could not fetch auth status. Is the backend running?");
    }
  };

  // --- Upload Handlers ---

  const handleFile = useCallback(async (file: File) => {
    if (!file.name.endsWith(".zip")) {
      setUploadError("Please upload a .zip file");
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setUploadResult(null);
    setUploadError(null);

    try {
      const result = await uploadExport(file, setUploadProgress);
      const totalRecords = Object.values(result.summary).reduce((a, b) => a + b, 0);
      setUploadResult(
        `Imported ${totalRecords.toLocaleString()} records successfully.`
      );
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Upload failed unexpectedly";
      setUploadError(message);
    } finally {
      setUploading(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  // --- Auth Handlers ---

  const handleConnect = () => {
    const authUrl = getAuthUrl();
    window.open(authUrl, "_blank");
  };

  // --- Sync Handlers ---

  const handleSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    setSyncError(null);
    try {
      const result = await triggerSync();
      setSyncResult(result);
      await fetchAuthStatus();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Sync failed unexpectedly";
      setSyncError(message);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <SettingsIcon size={24} />
        <h2>Settings</h2>
      </div>

      <div className="settings-grid">
        {/* Upload Section */}
        <div className="card">
          <div className="card-header">
            <Upload size={20} />
            <h3>Import Fitbit Export</h3>
          </div>
          <p className="card-description">
            Upload your Fitbit data export (.zip) to populate the dashboard with
            your historical health data.
          </p>

          <div
            className={`drop-zone ${dragOver ? "drag-over" : ""} ${uploading ? "uploading" : ""}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              onChange={handleFileSelect}
              style={{ display: "none" }}
            />
            <FileArchive size={40} className="drop-zone-icon" />
            {uploading ? (
              <div className="upload-progress-container">
                <div className="upload-progress-bar">
                  <div
                    className="upload-progress-fill"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <span className="upload-progress-text">
                  Uploading... {uploadProgress}%
                </span>
              </div>
            ) : (
              <>
                <p className="drop-zone-text">
                  Drop your Fitbit export .zip here
                </p>
                <p className="drop-zone-sub">or click to browse</p>
              </>
            )}
          </div>

          {uploadResult && (
            <div className="status-message success">
              <CheckCircle size={16} />
              <span>{uploadResult}</span>
            </div>
          )}
          {uploadError && (
            <div className="status-message error">
              <XCircle size={16} />
              <span>{uploadError}</span>
            </div>
          )}
        </div>

        {/* Auth Section */}
        <div className="card">
          <div className="card-header">
            <Link size={20} />
            <h3>Fitbit Connect</h3>
          </div>
          <p className="card-description">
            Connect your Fitbit account to sync data directly via the Fitbit Web
            API.
          </p>

          <div className="auth-status-block">
            <div className="auth-status-row">
              <span className="auth-status-label">Status</span>
              {authStatus ? (
                <span
                  className={`auth-status-badge ${authStatus.authenticated ? "connected" : "disconnected"}`}
                >
                  {authStatus.authenticated ? (
                    <>
                      <CheckCircle size={14} /> Connected
                    </>
                  ) : (
                    <>
                      <XCircle size={14} /> Not connected
                    </>
                  )}
                </span>
              ) : authError ? (
                <span className="auth-status-badge disconnected">
                  <AlertCircle size={14} /> Unknown
                </span>
              ) : (
                <span className="auth-status-badge loading">Loading...</span>
              )}
            </div>

            {authStatus?.expires_at && (
              <div className="auth-status-row">
                <span className="auth-status-label">Token expires</span>
                <span className="auth-status-value">
                  {new Date(authStatus.expires_at * 1000).toLocaleString()}
                </span>
              </div>
            )}
          </div>

          <button
            className="btn btn-primary"
            onClick={handleConnect}
          >
            <Link size={16} />
            {authStatus?.authenticated ? "Reconnect Fitbit" : "Connect Fitbit"}
          </button>

          {authError && (
            <div className="status-message error">
              <AlertCircle size={16} />
              <span>{authError}</span>
            </div>
          )}
        </div>

        {/* Sync Section */}
        <div className="card">
          <div className="card-header">
            <RefreshCw size={20} />
            <h3>Sync Data</h3>
          </div>
          <p className="card-description">
            Manually trigger a data sync from the Fitbit API. Requires an active
            connection above.
          </p>

          <button
            className="btn btn-primary"
            onClick={handleSync}
            disabled={syncing || !authStatus?.authenticated}
          >
            <RefreshCw size={16} className={syncing ? "spin" : ""} />
            {syncing ? "Syncing..." : "Sync Now"}
          </button>

          {syncResult && (
            <div className="status-message success">
              <CheckCircle size={16} />
              <span>{syncResult.message}</span>
            </div>
          )}
          {syncError && (
            <div className="status-message error">
              <XCircle size={16} />
              <span>{syncError}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
