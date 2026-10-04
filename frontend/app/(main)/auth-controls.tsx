"use client";

import {
  SignInButton,
  SignUpButton,
  UserButton,
  useUser,
} from "@clerk/nextjs";
import { PersonalDetailsForm } from "./personal-details";

const clerkConfigured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

function SignedInControls() {
  const { isLoaded, isSignedIn } = useUser();

  if (!isLoaded) return <span className="auth-guest-note">Account</span>;

  if (isSignedIn) {
    return (
      <div className="auth-user-control" aria-label="Your account">
        <span className="auth-user-label">Account</span>
        <UserButton>
          <UserButton.UserProfilePage 
            label="Personal Details" 
            url="personal-details" 
            labelIcon={
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            }
          >
            <PersonalDetailsForm />
          </UserButton.UserProfilePage>
        </UserButton>
      </div>
    );
  }

  return (
    <div className="auth-controls" aria-label="Account access">
      <span className="auth-guest-note">You can continue as a guest.</span>
      <SignInButton mode="modal">
        <button className="auth-button auth-button-quiet" type="button">Sign in</button>
      </SignInButton>
      <SignUpButton mode="modal">
        <button className="auth-button auth-button-primary" type="button">Create account</button>
      </SignUpButton>
    </div>
  );
}

export default function AuthControls() {
  if (!clerkConfigured) {
    return <span className="auth-guest-note">Guest access</span>;
  }

  return <SignedInControls />;
}
