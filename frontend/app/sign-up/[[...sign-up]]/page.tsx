import { SignUp } from "@clerk/nextjs";
import { AuthFrame, clerkAppearance } from "@/app/auth-frame";

export default function SignUpPage() {
  return (
    <AuthFrame>
      <SignUp appearance={clerkAppearance} signInUrl="/sign-in" fallbackRedirectUrl="/onboarding" />
    </AuthFrame>
  );
}
