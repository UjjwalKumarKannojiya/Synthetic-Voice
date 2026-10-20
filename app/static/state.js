const profileKey = "voiceguard.model-profile";

export const state = {
  profile: ["legacy_for2sec", "asvspoof_la_balanced2500"].includes(localStorage.getItem(profileKey))
    ? localStorage.getItem(profileKey)
    : "legacy_for2sec",
  live: null,
};

export function setProfile(profile) {
  state.profile = profile;
  localStorage.setItem(profileKey, profile);
}
