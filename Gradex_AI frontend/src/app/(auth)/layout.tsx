"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { LoginPage } from "@/components/LoginPage";
import { Toaster } from "@/components/ui/sonner";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { role, setRole } = useAuth();

  if (role) {
    router.push(role === "lecturer" ? "/dashboard" : "/student-dashboard");
    return null;
  }

  return (
    <>
      <LoginPage
        onLogin={(r) => {
          setRole(r);
          router.push(r === "lecturer" ? "/dashboard" : "/student-dashboard");
        }}
      />
      <Toaster />
    </>
  );
}
