"use client"

import { useCallback, useState } from "react"

import ResetPasswordForm, { type ResetPasswordFormValues } from "@/components/ui/ResetPasswordForm"
import { toaster, Toaster } from "@/components/ui/toaster"

interface ResetPasswordProps {
  uid?: string
  token?: string
}

interface ResetPasswordResponse {
  detail?: string | string[]
}

const RESET_PASSWORD_ENDPOINT = "/api/auth/reset-password"

export default function ResetPassword({ uid, token }: ResetPasswordProps) {
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(() =>
    uid && token ? null : "This password reset link is invalid or incomplete.",
  )
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const handleSubmit = useCallback(
    async (values: ResetPasswordFormValues) => {
      setErrorMessage(null)
      setSuccessMessage(null)

      if (!uid || !token) {
        setErrorMessage("This password reset link is invalid or incomplete.")
        return
      }

      if (values.password !== values.confirmPassword) {
        setErrorMessage("The passwords do not match.")
        return
      }

      setLoading(true)
      try {
        const response = await fetch(RESET_PASSWORD_ENDPOINT, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uid, token, password: values.password }),
          cache: "no-store",
        })

        const data = (await response.json().catch(() => ({}))) as ResetPasswordResponse

        if (!response.ok) {
          toaster.create({
            title: "Password reset failed",
            description: data.detail ?? "Unable to reset your password. Please try again.",
            type: "info",
            closable: true,
          })

          return
        }

        setSuccessMessage(
          typeof data.detail === "string"
            ? data.detail
            : "Your password has been reset. You can now sign in.",
        )
      } catch (error) {
        console.error("Password reset failed", error)
        setErrorMessage("Unable to reach the server. Please try again.")
      } finally {
        setLoading(false)
      }
    },
    [token, uid],
  )

  return (
    <>
      <Toaster />
      <ResetPasswordForm
        defaultValues={{ password: "", confirmPassword: "" }}
        loading={loading}
        errorMessage={errorMessage}
        successMessage={successMessage}
        onSubmit={handleSubmit}
      />
    </>
  )
}
