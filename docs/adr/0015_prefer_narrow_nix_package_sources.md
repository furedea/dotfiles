# ADR-0015: Prefer narrow Nix package sources

- Status: Accepted
- Date: 2026-08-24

In the context of sourcing user-facing CLI packages from stable Nixpkgs,
unstable Nixpkgs, upstream flakes, and local derivations, facing stale pins and
global package-set changes that outlive their original need, we decided for
stable Nixpkgs by default, unstable Nixpkgs or upstream flakes when their update
cadence is intentional, local `callPackage` derivations for configuration-scoped
packages and overrides, and overlays only when consumers must share a
package-set-wide replacement, and against adding every missing or customized
CLI through an overlay, to minimize fixed-point changes and make upstream
transitions explicit, accepting that package selection still requires explicit
judgment and local overrides remain necessary for behavior such as additional
shell completions.
