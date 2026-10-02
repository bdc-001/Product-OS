import { SignIn } from "@clerk/nextjs";
import { AuthFrame, clerkAppearance } from "@/app/auth-frame";

export default function SignInPage() {
  return (
    <AuthFrame>
      <SignIn appearance={clerkAppearance} signUpUrl="/sign-up" fallbackRedirectUrl="/" />
    </AuthFrame>
  );
}
