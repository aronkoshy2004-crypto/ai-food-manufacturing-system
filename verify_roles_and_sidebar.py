"""
Automated Verification Script for Role-Based Routing, Sidebar Structure, and Route Protection
"""
import urllib.request
import urllib.parse
import http.cookiejar
import re
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_role_flow(role_name, expected_landing, forbidden_url):
    print(f"\n==========================================")
    print(f"Testing Role: {role_name}")
    print(f"==========================================")
    
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPRedirectHandler()
    )

    # 1. Test Demo Login
    demo_url = f"{BASE_URL}/demo-login/{role_name}"
    req = urllib.request.Request(demo_url, headers={"User-Agent": "FoodManTester/1.0"})
    resp = opener.open(req)
    final_url = resp.geturl()
    
    # Expected relative landing path
    expected_full = f"{BASE_URL}{expected_landing}"
    print(f"1. Landing Page Check:")
    print(f"   Target Expected : {expected_full}")
    print(f"   Actual Final URL: {final_url}")
    assert expected_landing in final_url, f"Landing mismatch for {role_name}: expected {expected_landing}, got {final_url}"
    print(f"   [PASS] Landed accurately on {expected_landing}")

    # Read page content
    html = resp.read().decode('utf-8')

    # 2. Check Sidebar Groups in rendered HTML
    print(f"2. Sidebar Workflow Groups Check:")
    groups_found = []
    if "Suppliers & Raw Materials" in html: groups_found.append("1. SUPPLIERS & RAW MATERIALS")
    if "Purchase Management" in html: groups_found.append("2. PURCHASE MANAGEMENT")
    if "QC & AI Inspection" in html: groups_found.append("3. QC & AI INSPECTION")
    if "Batch & Production" in html: groups_found.append("4. BATCH & PRODUCTION")
    if "Warehouse Management" in html: groups_found.append("5. WAREHOUSE MANAGEMENT")
    if "Dispatch & Traceability" in html: groups_found.append("6. DISPATCH & TRACEABILITY")
    if "Reports & Analytics" in html: groups_found.append("7. REPORTS & ANALYTICS")
    if "Alerts & Notifications" in html: groups_found.append("8. ALERTS & NOTIFICATIONS")

    for g in groups_found:
        print(f"   [OK] Visible Group: {g}")

    # Role-specific checks
    if role_name.lower() == 'procurement':
        assert "Suppliers & Raw Materials" in html
        assert "Purchase Management" in html
        assert "QC & AI Inspection" not in html
        assert "Batch & Production" not in html
        assert "Warehouse Management" not in html
        assert "Reports & Analytics" not in html
    elif role_name.lower() == 'qc':
        assert "QC & AI Inspection" in html
        assert "Suppliers & Raw Materials" not in html
        assert "Purchase Management" not in html
        assert "Batch & Production" not in html
        assert "Warehouse Management" not in html
        assert "Reports & Analytics" not in html
    elif role_name.lower() == 'production':
        assert "Batch & Production" in html
        assert "Suppliers & Raw Materials" not in html
        assert "QC & AI Inspection" not in html
        assert "Warehouse Management" not in html
        assert "Reports & Analytics" not in html
    elif role_name.lower() == 'warehouse':
        assert "Warehouse Management" in html
        assert "Dispatch & Traceability" in html
        assert "Suppliers & Raw Materials" not in html
        assert "QC & AI Inspection" not in html
        assert "Batch & Production" not in html
        assert "Reports & Analytics" not in html
    elif role_name.lower() == 'admin':
        assert len(groups_found) == 8, f"Admin should see all 8 groups, but found {len(groups_found)}"

    print(f"   [PASS] Sidebar groups strictly match {role_name} scope.")

    # 3. Route-Level Protection Check: directly access forbidden URL
    if forbidden_url:
        print(f"3. Route Protection Check against: {forbidden_url}")
        target_forbidden = f"{BASE_URL}{forbidden_url}"
        req_forbid = urllib.request.Request(target_forbidden, headers={"User-Agent": "FoodManTester/1.0"})
        resp_forbid = opener.open(req_forbid)
        redirected_url = resp_forbid.geturl()
        content_forbid = resp_forbid.read().decode('utf-8')
        
        print(f"   Target Forbidden  : {target_forbidden}")
        print(f"   Redirected URL    : {redirected_url}")
        
        # User must NOT remain on forbidden URL
        assert forbidden_url not in redirected_url, f"Role {role_name} was NOT blocked from {forbidden_url}!"
        assert expected_landing in redirected_url, f"Redirected to unexpected URL: {redirected_url}"
        
        # Check flash alert message
        assert "Access restricted" in content_forbid or "not authorized" in content_forbid
        print(f"   [PASS] Forbidden route was blocked & redirected to workspace with alert banner.")

def main():
    print("Starting verification of 5 Roles and 8 Workflow Groups...")
    
    test_cases = [
        ("Admin", "/dashboard", None),
        ("Procurement", "/procurement?view=suppliers", "/qc"),
        ("QC", "/qc?view=queue", "/production"),
        ("Production", "/production?view=batches", "/dashboard"),
        ("Warehouse", "/warehouse?view=inventory", "/reports"),
    ]

    for role, landing, forbidden in test_cases:
        test_role_flow(role, landing, forbidden)

    print("\n" + "="*50)
    print("ALL TESTS PASSED! ROLES & SIDEBAR FULLY VERIFIED.")
    print("="*50)

if __name__ == "__main__":
    main()
