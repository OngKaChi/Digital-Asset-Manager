"use client"

import {
    Button,
    Card,
    Heading,
    Input,
    Link,
    Stack,
    Text,
    chakra,
} from "@chakra-ui/react"
import { useId, useMemo, useState, type FormEvent } from "react"

export type ForgotPasswordFormValues = {
    email: string
}

export interface ForgotPasswordFormProps {
    defaultValues?: Partial<ForgotPasswordFormValues>
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
    onSubmit?: (values: ForgotPasswordFormValues) => void | Promise<void>
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

export function ForgotPasswordForm({
    defaultValues,
    loading = false,
    errorMessage,
    successMessage,
    onSubmit,
    title = "Forgot password?",
    subtitle = "Enter your email and receive a password reset link.",
}: ForgotPasswordFormProps) {
    const emailId = useId()

    const [email, setEmail] = useState(() => defaultValues?.email ?? "")

    const submitDisabled = useMemo(
        () => loading || email.trim().length === 0,
        [loading, email],
    )

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault()
        if (!onSubmit) return

        await onSubmit({
            email: email.trim(),
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
            bg={{ base: 'white', _dark: 'gray.800' }}
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
                    <Text
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
                ) : null}

                <chakra.form onSubmit={handleSubmit}>
                    <Stack gap="5">
                        <Stack gap="2">
                            <Label htmlFor={emailId} fontWeight="medium">
                                Email
                            </Label>
                            <Input
                                id={emailId}
                                type="email"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                placeholder="you@example.com"
                                autoComplete="email"
                                variant="outline"
                                borderColor={{ base: "gray.200", _dark: "whiteAlpha.400" }}
                                required
                            />
                        </Stack>

                        <Button
                            type="submit"
                            loading={loading}
                            disabled={submitDisabled}
                            colorPalette="blue"
                        >
                            Send reset link
                        </Button>
                    </Stack>
                    <Link href="/" style={{ display: 'block', marginTop: '1rem', textAlign: 'center', fontSize: '0.875rem', color: '#3182ce' }}>
                        Back to login
                    </Link>
                </chakra.form>
            </Stack>
        </Card.Root>
    )
}

export default ForgotPasswordForm