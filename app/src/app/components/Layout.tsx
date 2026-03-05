import { Outlet, Link, useLocation } from "react-router-dom"
import {
  FileText,
  FilePlus,
  FolderOpen,
  User,
  Building2,
  LogOut
} from "lucide-react"
import { useAuth } from "react-oidc-context"

export function Layout() {
  const location = useLocation()
  const auth = useAuth()

  const navItems = [
    { path: "/create-review", label: "Create a Review", icon: FilePlus },
    { path: "/past-reviews", label: "View Past Reviews", icon: FileText },
    { path: "/my-documents", label: "View My Documents", icon: FolderOpen },
    { path: "/my-details", label: "My Details", icon: User }
  ]

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <Link to="/" className="flex items-center gap-2">
            <Building2 className="w-8 h-8 text-blue-600" />
            <div>
              <h1 className="font-semibold text-lg">Hospital Review</h1>
              <p className="text-xs text-gray-500">Transparent Healthcare</p>
            </div>
          </Link>
        </div>

        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path

              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-700 hover:bg-gray-100"
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <span className="text-sm font-medium">{item.label}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* User profile + sign-out */}
        <div className="p-4 border-t border-gray-200">
          {auth.user ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3 min-w-0">
                {auth.user.profile?.picture ? (
                  <img
                    src={auth.user.profile.picture}
                    alt={auth.user.profile?.name || "User"}
                    className="w-8 h-8 rounded-full flex-shrink-0 object-cover"
                  />
                ) : (
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                    <span className="text-blue-600 text-sm font-semibold">
                      {(auth.user.profile?.name || "U").charAt(0).toUpperCase()}
                    </span>
                  </div>
                )}
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {auth.user.profile?.name || "User"}
                  </p>
                  <p className="text-xs text-gray-500 truncate">{auth.user.profile?.email}</p>
                </div>
              </div>
              {/* Sign-out always visible when user is present */}
              <button
                onClick={() => auth.signoutRedirect()}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </button>
            </div>
          ) : (
            <div className="text-xs text-gray-500">
              <p className="font-medium mb-1">Healthcare Transparency</p>
              <p>Empowering informed decisions for everyone</p>
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
