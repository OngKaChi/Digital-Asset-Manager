"use client"

import { useCallback, useState } from "react"

import ForgotPasswordForm, { type ForgotPasswordFormValues } from "@/components/ui/ForgotPasswordForm"
import { toaster, Toaster } from "@/components/ui/toaster"

interface ForgotPasswordResponse {
  detail?: string | string[]
}

const FORGOT_PASSWORD_ENDPOINT = "/api/auth/forgot-password"

export default function ForgotPasswordView() {
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const handleSubmit = useCallback(
    async (values: ForgotPasswordFormValues) => {
      setLoading(true)
      setErrorMessage(null)
      setSuccessMessage(null)

      try {
        const response = await fetch(FORGOT_PASSWORD_ENDPOINT, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(values),
          cache: "no-store",
        })

        const data = (await response.json().catch(() => ({}))) as ForgotPasswordResponse

        if (!response.ok) {
          toaster.create({
            title: "Password reset request failed",
            description: data.detail ?? "Unable to request a password reset. Please try again.",
            type: "info",
            closable: true,
          })
          return
        } 

        if (data.detail) {
          toaster.create({
            title: "Password reset request successful",
            description: data.detail ?? "The password reset request was successful. Please check your email for the reset link.",
            type: "info",
            closable: true,
          })
        }

      } catch (error) {
        console.error("Password reset request failed", error)
        setErrorMessage("Unable to reach the server. Please try again.")
      } finally {
        setLoading(false)
      }
    },
    []
  )

  return (
    <><Toaster />
    <ForgotPasswordForm
      defaultValues={{ email: "" }}
      loading={loading}
      errorMessage={errorMessage}
      successMessage={successMessage}
      onSubmit={handleSubmit}
    />
    </>
  )
}
