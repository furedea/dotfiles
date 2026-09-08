# Config and Serialization

- Use typed structs for project-owned config.
- Use `serde(deny_unknown_fields)` where unknown input keys should be rejected.
- Do not reject unknown keys in external-tool-owned config files.
- Use `#[serde(rename_all = "...")]` to keep serialized field naming consistent.
- Use `#[serde(default)]` for optional input fields that have stable defaults.
- Use `#[serde(skip_serializing_if = "Option::is_none")]` when absent values should not appear in output.
- Use `#[serde(flatten)]` sparingly because it makes schemas less explicit.
- Separate fully generated files from user-owned files that receive managed updates.
- Do not overwrite user-owned or external-tool-owned config files wholesale.
- For managed config sync, update only the keys owned by the project and preserve unknown keys.
- Use stable ordering for generated output when review diffs or tests depend on order.
- Use a format-preserving edit strategy when comments, ordering, and unknown future keys must be preserved.
