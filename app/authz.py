# app/authz.py
import json
import logging
import os
import re
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

# --- Logger Setup ---
log = logging.getLogger(__name__)
IS_AUTH_DEBUG = os.getenv("AUTH_DEBUG", "false").lower() == "true"


class AuthzEngine:
    """
    A pluggable, policy-based authorization engine.
    It makes decisions by evaluating rules defined in JSON files against a user's
    identity (JWT claims) and the runtime request context.
    """

    def __init__(
        self, public_map_path="app/public.map.json", authz_map_path="app/authz.map.json"
    ):
        self.public_map_path = public_map_path
        self.authz_map_path = authz_map_path
        self.load_policies()

    def load_policies(self):
        """
        Loads the authorization policies from JSON files into memory.
        This method is called once on startup.
        """
        log.info("Loading authorization policies from disk...")
        try:
            with open(self.public_map_path, "r") as f:
                self._public_paths = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._public_paths = []
            log.warning(
                f"Public map not found or invalid at {self.public_map_path}. No public paths will be configured."
            )

        try:
            with open(self.authz_map_path, "r") as f:
                self._authz_rules = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._authz_rules = {}
            log.warning(
                f"Authz map not found or invalid at {self.authz_map_path}. All non-public paths will be denied."
            )

        log.info("Policies loaded successfully.")

    def _resolve_value(
        self, placeholder: str, user: dict, request: Request, context: dict
    ):
        """
        Resolves a placeholder string (e.g., "{user.sub}", "{path.doc_id}", "{context.resource.owner_id}")
        to its actual runtime value. If the value is not a placeholder, it's returned directly.
        """
        if (
            not isinstance(placeholder, str)
            or not placeholder.startswith("{")
            or not placeholder.endswith("}")
        ):
            return placeholder

        path = placeholder.strip("{}")
        parts = path.split(".")
        source = parts[0]

        value = None
        if source == "user":
            value = user
        elif source == "path":
            value = request.path_params
        elif source == "context":
            value = context
        else:
            return placeholder

        # Traverse the nested dictionary (e.g., context -> resource -> owner_id)
        for part in parts[1:]:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _evaluate_rule(
        self, rule: dict, user: dict, user_roles: set, request: Request, context: dict
    ) -> bool:
        """
        Recursively evaluates a rule object against the full request and user context.
        This is the core of the decision-making logic.
        """
        # --- LOGICAL OPERATORS ---
        if "NOT" in rule:
            condition_to_negate = rule["NOT"]
            if isinstance(condition_to_negate, str):
                return not (condition_to_negate in user_roles)
            elif isinstance(condition_to_negate, dict):
                return not self._evaluate_rule(
                    condition_to_negate, user, user_roles, request, context
                )
            return False

        if "ALL" in rule:
            return all(
                (
                    self._evaluate_rule(sub, user, user_roles, request, context)
                    if isinstance(sub, dict)
                    else sub in user_roles
                )
                for sub in rule["ALL"]
            )
        if "ANY" in rule:
            return any(
                (
                    self._evaluate_rule(sub, user, user_roles, request, context)
                    if isinstance(sub, dict)
                    else sub in user_roles
                )
                for sub in rule["ANY"]
            )

        # --- VALUE & COMPARISON OPERATORS ---
        if "claims" in rule:
            for key_placeholder, val_placeholder in rule["claims"].items():
                actual = self._resolve_value(key_placeholder, user, request, context)
                expected = self._resolve_value(val_placeholder, user, request, context)
                if actual != expected:
                    if IS_AUTH_DEBUG:
                        log.debug(f"Check failed [claims]: '{actual}' != '{expected}'")
                    return False
            return True

        if "claims_lte" in rule:  # Less Than or Equal To
            for key_placeholder, val_placeholder in rule["claims_lte"].items():
                actual = self._resolve_value(key_placeholder, user, request, context)
                expected = self._resolve_value(val_placeholder, user, request, context)
                if not (
                    isinstance(actual, (int, float))
                    and isinstance(expected, (int, float))
                    and actual <= expected
                ):
                    if IS_AUTH_DEBUG:
                        log.debug(
                            f"Check failed [claims_lte]: '{actual}' is not <= '{expected}'"
                        )
                    return False
            return True

        if "claims_gte" in rule:  # Greater Than or Equal To
            for key_placeholder, val_placeholder in rule["claims_gte"].items():
                actual = self._resolve_value(key_placeholder, user, request, context)
                expected = self._resolve_value(val_placeholder, user, request, context)
                if not (
                    isinstance(actual, (int, float))
                    and isinstance(expected, (int, float))
                    and actual >= expected
                ):
                    if IS_AUTH_DEBUG:
                        log.debug(
                            f"Check failed [claims_gte]: '{actual}' is not >= '{expected}'"
                        )
                    return False
            return True

        if "claims_contains" in rule:  # List membership
            for key_placeholder, val_placeholder in rule["claims_contains"].items():
                list_to_check = self._resolve_value(
                    key_placeholder, user, request, context
                )
                value_to_find = self._resolve_value(
                    val_placeholder, user, request, context
                )
                if not (
                    isinstance(list_to_check, list) and value_to_find in list_to_check
                ):
                    if IS_AUTH_DEBUG:
                        log.debug(
                            f"Check failed [claims_contains]: '{value_to_find}' not in list."
                        )
                    return False
            return True

        if "claims_timediff_lte" in rule:  # Step-up auth recency
            for key, seconds in rule["claims_timediff_lte"].items():
                claim_ts = self._resolve_value(
                    f"{{user.{key}}}", user, request, context
                )
                if not isinstance(claim_ts, int):
                    return False
                diff = int(datetime.now(timezone.utc).timestamp()) - claim_ts
                if diff > seconds:
                    if IS_AUTH_DEBUG:
                        log.debug(
                            f"Check failed [claims_timediff_lte]: {key} was {diff}s ago (limit {seconds}s)."
                        )
                    return False
            return True

        return False

    def check(self, request: Request, user: dict | None, context: dict = None):
        """
        The main public method for authorization. It orchestrates the entire check.
        Raises HTTPException on failure, returns True on success.
        """
        context = context or {}
        request_path = request.url.path

        # Dynamically get the base_path from the environment.
        base_path = os.getenv("BASE_PATH", "")

        # 1. Check if the path is whitelisted as public.
        # We prepend the base_path to the public path rules for matching.
        if any(
            re.fullmatch(f"{base_path}{p}", request_path) for p in self._public_paths
        ):
            if IS_AUTH_DEBUG:
                log.debug(f"Decision: ALLOW. Reason: Path '{request_path}' is public.")
            return True

        # 2. If not public, a user must be authenticated.
        if user is None:
            if IS_AUTH_DEBUG:
                log.debug(
                    f"Decision: DENY. Reason: Path '{request_path}' is protected and requires authentication."
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            )

        # 3. Find a matching rule in the policy map.
        for rule_path, rule in self._authz_rules.items():
            # CRITICAL CHANGE: Construct the full, expected path from the base_path and the rule key.
            full_rule_path = f"{base_path}{rule_path}"

            if re.fullmatch(full_rule_path, request_path):
                # 3a. Handle simple "authenticated-only" rule (e.g., "ALL": [] or {}).
                rule_is_simple_auth = not rule or (
                    isinstance(rule.get("ALL"), list) and not rule.get("ALL")
                )

                if rule_is_simple_auth or not any(
                    op in rule
                    for op in [
                        "ANY",
                        "ALL",
                        "NOT",
                        "claims",
                        "claims_lte",
                        "claims_gte",
                        "claims_contains",
                        "claims_timediff_lte",
                    ]
                ):
                    if IS_AUTH_DEBUG:
                        log.debug(
                            f"Decision: ALLOW. Reason: Path '{request_path}' requires basic authentication."
                        )
                    return True

                # 3b. Extract user roles for evaluation.
                realm_roles = user.get("realm_access", {}).get("roles", [])
                client_id = os.getenv("KEYCLOAK_CLIENT_ID")
                client_roles = (
                    user.get("resource_access", {}).get(client_id, {}).get("roles", [])
                )
                user_roles = set(realm_roles + client_roles)

                # 3c. Evaluate the complex rule.
                if self._evaluate_rule(rule, user, user_roles, request, context):
                    if IS_AUTH_DEBUG:
                        log.debug(
                            f"Decision: ALLOW. Reason: User satisfies rule for '{request_path}'."
                        )
                    return True
                else:
                    # The rule evaluation failed, so deny access.
                    # No need to log here as _evaluate_rule already logs the specific failure.
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions.",
                    )

        # 4. Secure by Default: If a path is not public and has no matching rule, deny access.
        if IS_AUTH_DEBUG:
            log.debug(
                f"Decision: DENY. Reason: No authorization rule for protected path '{request_path}'."
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this resource is not configured.",
        )
