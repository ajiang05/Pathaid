import type { Metadata } from "next"; import { ProfileForm } from "@/components/profile-form";
export const metadata:Metadata={title:"Build your profile"}; export default function Onboarding(){return <ProfileForm mode="onboarding"/>}
