# What keeps T3 Code from sending telemetry, shared by the darwin and Home Manager modules
# and checked by nix/checks.nix (ADR-0048).
rec {
  envName = "T3CODE_TELEMETRY_ENABLED";
  envValue = "false";

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
