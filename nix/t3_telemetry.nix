# What keeps T3 Code from sending telemetry, shared by the darwin and Home Manager modules
# and checked by nix/checks.nix (ADR-0048).
rec {
  envName = "T3CODE_TELEMETRY_ENABLED";
  envValue = "false";

  # Redundant with the opt-out above: relay tracing needs telemetry on and OTel export enabled, so either
  # variable stops it. The generic OTEL_SDK_DISABLED is not set: it would affect other tools.
  otelEnvName = "T3CODE_OTEL_SDK_DISABLED";
  otelEnvValue = "true";

  # Product events go to ingest.t3.codes, relay traces to api.axiom.co; T3 Connect is unused (ADR-0045).
  blockedHosts = [
    "ingest.t3.codes"
    "api.axiom.co"
    "relay.t3.codes"
  ];

  policyDirectory = "/Library/Application Support/T3Code";
  policyFile = "${policyDirectory}/policy.json";
  policy = {
    schemaVersion = 1;
    organization = "dotfiles";
    limits.telemetry = false;
  };

  serverLabel = "org.nix-community.home.t3-server";
}
