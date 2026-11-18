"use client";

import React, { useState } from "react";
import { Modal } from "../ui/modal";
import { Button } from "../ui/button";
import { authApi } from "../../lib/api/client";
import { useAuthStore } from "../../lib/store/auth";
import { useOrgStore } from "../../lib/store/org";

const ACCOUNT_TYPES = [
  { id: "individual", label: "Individual Developer", desc: "Personal repositories & codebase Q&A" },
  { id: "freelancer", label: "Freelancer", desc: "Separate workspaces for client codebases" },
  { id: "agency", label: "Software Agency", desc: "Multi-client projects & team onboarding" },
  { id: "startup", label: "Startup", desc: "Shared engineering hub & faster ramp-up" },
  { id: "enterprise", label: "Enterprise", desc: "Multi-team governance & isolated orgs" },
];

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function OnboardingModal({ isOpen, onClose }: OnboardingModalProps) {
  const { initialize } = useAuthStore();
  const { loadOrgs } = useOrgStore();
  const [accountType, setAccountType] = useState("startup");
  const [workspaceName, setWorkspaceName] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSave = async (skip = false) => {
    setSaving(true);
    try {
      await authApi.completeOnboarding({
        account_type: skip ? "individual" : accountType,
        workspace_name: !skip && workspaceName.trim().length >= 2 ? workspaceName.trim() : undefined,
      });
      await initialize();
      await loadOrgs();
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={() => !saving && onClose()}
      title="Set Up Your TrunkHQ Workspace"
      description="Select how you use TrunkHQ so we can tailor your organization workspace."
      maxWidth="md"
    >
      <div className="space-y-4 pt-2">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {ACCOUNT_TYPES.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setAccountType(item.id)}
              className={`rounded-lg border p-3 text-left transition ${
                accountType === item.id
                  ? "border-emerald-500 bg-emerald-500/12"
                  : "border-border-default bg-bg-primary/60 hover:border-text-tertiary"
              }`}
            >
              <p className="text-xs font-semibold text-text-primary">{item.label}</p>
              <p className="text-[11px] text-text-secondary mt-0.5">{item.desc}</p>
            </button>
          ))}
        </div>

        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">
            Workspace / Organization Name (optional)
          </label>
          <input
            type="text"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
            placeholder="e.g. Acme Engineering or Client Projects"
            className="w-full rounded-lg border border-border-default bg-bg-primary px-3 py-2 text-xs text-text-primary placeholder:text-text-tertiary focus:border-emerald-500 focus:outline-none"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={saving}
            onClick={() => handleSave(true)}
          >
            Skip for now
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            isLoading={saving}
            onClick={() => handleSave(false)}
          >
            Continue to Workspace
          </Button>
        </div>
      </div>
    </Modal>
  );
}
