"use client"

import { Button, Card, Heading, Link, Stack, Text, chakra } from "@chakra-ui/react"
import { type FormEvent, useMemo, useState } from "react"

import { PasswordInput } from "@/components/ui/password-input"

export type ResetPasswordFormValues = {
  password: string
  confirmPassword: string
}

export interface ResetPasswordFormProps {
    defaultValues?: Partial<ResetPasswordFormValues>
    /**
     * Controls the loading state of the submit button.
     */
    loading?: boolean
    /**
     * Message shown when authentication fails.
     */
    errorMessage?: string | null
    /**
     * Message shown when authentication succeeds.
     */
    successMessage?: string | null
    /**
     * Callback invoked after submit with the latest field values.
     */
    onSubmit?: (values: ResetPasswordFormValues) => void | Promise<void>
    /**
     * Optional heading text displayed at the top of the card.
     */
    title?: string
    /**
     * Optional helper text shown under the heading.
     */
    subtitle?: string
}

const Label = chakra("label")

export function ResetPasswordForm({
  defaultValues,
  loading = false,
  errorMessage,
  successMessage,
  onSubmit,
  title = "Set a new password",
  subtitle = "Choose a new password for your account.",
}: ResetPasswordFormProps) {

    const [password, setPassword] = useState(() => defaultValues?.password ?? "")
    const [confirmPassword, setConfirmPassword] = useState(() => defaultValues?.confirmPassword ?? "")

    const submitDisabled = useMemo(
        () => loading || password.trim().length === 0 || confirmPassword.trim().length === 0,
        [loading, password, confirmPassword],
    )

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (!onSubmit) return

        await onSubmit({
            password: password.trim(),
            confirmPassword: confirmPassword.trim(),
        })
    }

    return (
        <Card.Root
            shadow="lg"
            borderRadius="2xl"
            padding="8"
            width="md"
            maxW="md"
            background="white"
            borderWidth="1px"
            bg={{ base: "white", _dark: "gray.800" }}
        >
            <Stack gap="6">
                <Stack gap="1">
                    <Heading size="lg">{title}</Heading>
                    {subtitle ? (
						<Text fontSize="sm">
							{subtitle}
						</Text>
					) : null}
                </Stack>

                {errorMessage ? (
                    <Text 
						role="alert"
						color="red.500"
						fontWeight="medium"
						background="red.50"
						borderRadius="lg"
						borderWidth="1px"
						borderColor="red.200"
						padding="3"
					>
						{errorMessage}
                    </Text>
                ) : null}

				{!errorMessage && successMessage ? (
					<><Text
                        role="status"
                        color="green.600"
                        fontWeight="medium"
                        background="green.50"
                        borderRadius="lg"
                        borderWidth="1px"
                        borderColor="green.200"
                        padding="3"
                    >
                        {successMessage}
                    </Text>
                    <Text>
                        <Link href="/" style={{ display: 'block', marginTop: '1rem', textAlign: 'center', fontSize: '0.875rem', color: '#3182ce' }}>
                            Back to login
                        </Link>
                    </Text></>
				) : null}

                {!successMessage ? (
                    <chakra.form onSubmit={handleSubmit}>
                        <Stack gap="5">
                            <Stack gap="2">
                                <Label fontWeight="medium">
                                    New Password
                                </Label>
                                <PasswordInput
                                    aria-label="New password"
                                    value={password}
                                    onChange={(event) => setPassword(event.target.value)}
                                    placeholder="New password"
                                    autoComplete="new-password"
                                    borderColor={{ base: "gray.200", _dark: "whiteAlpha.400" }}
                                    required
                                />
                            </Stack>

                            <Stack gap="2">
                                <Label fontWeight="medium">
                                    Confirm Password
                                </Label>
                                <PasswordInput
                                    aria-label="Confirm new password"
                                    value={confirmPassword}
                                    onChange={(event) => setConfirmPassword(event.target.value)}
                                    placeholder="Confirm new password"
                                    autoComplete="new-password"
                                    borderColor={{ base: "gray.200", _dark: "whiteAlpha.400" }}
                                    required
                                />
                            </Stack>

                            <Button type="submit" loading={loading} disabled={submitDisabled} colorPalette="blue">
                                Reset password
                            </Button>
                        </Stack>
                    </chakra.form>
                ) : null}
            </Stack>
        </Card.Root>
    )
}

export default ResetPasswordForm